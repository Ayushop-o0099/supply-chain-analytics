"""Dispatch-time features and chronological evaluation with outcome availability guards."""
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (precision_score, recall_score, f1_score, roc_auc_score,
                             average_precision_score, confusion_matrix)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from .analytics import load_performance
from .config import ROOT
from .database import engine_for, upsert
from .etl import utc_now

NUMERIC = ['weight_kg', 'distance_km', 'planned_transit_hours', 'dispatch_month', 'dispatch_weekday']
CATEGORICAL = ['carrier_id', 'route_id', 'service_level']


def features(df):
    out = df[['weight_kg', 'distance_km', 'carrier_id', 'route_id', 'service_level']].copy()
    dispatch = pd.to_datetime(df.dispatch_at, errors='raise', utc=True)
    promised = pd.to_datetime(df.promised_delivery_at, errors='raise', utc=True)
    out['planned_transit_hours'] = (promised-dispatch).dt.total_seconds()/3600
    out['dispatch_month'] = dispatch.dt.month
    out['dispatch_weekday'] = dispatch.dt.dayofweek
    for col in ['carrier_id', 'route_id']:
        out[col] = out[col].astype(str)
    if out[NUMERIC].isna().any().any() or not np.isfinite(out[NUMERIC].to_numpy(dtype=float)).all():
        raise ValueError('Prediction features contain missing or nonfinite values.')
    if (out[['weight_kg', 'distance_km', 'planned_transit_hours']] <= 0).any().any():
        raise ValueError('Weight, distance, and planned transit must be positive.')
    return out[NUMERIC+CATEGORICAL]


def chronological_split(df):
    ordered = df.sort_values('dispatch_at')
    validation_start = ordered.dispatch_at.iloc[int(len(ordered)*.70)]
    test_start = ordered.dispatch_at.iloc[int(len(ordered)*.85)]
    complete = ordered[ordered.status.eq('Delivered')]
    train = complete[(complete.dispatch_at < validation_start) & (complete.actual_delivery_at < validation_start)]
    validation = complete[(complete.dispatch_at >= validation_start) & (complete.dispatch_at < test_start)
                          & (complete.actual_delivery_at < test_start)]
    test = complete[complete.dispatch_at >= test_start]
    for name, part in [('train', train), ('validation', validation), ('test', test)]:
        if len(part) < 30 or part.is_delayed.nunique() != 2:
            raise ValueError(f'Insufficient rows or target classes in {name} split.')
    return train, validation, test, validation_start, test_start


def pipeline(classifier):
    numeric = Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())])
    categorical = Pipeline([('impute', SimpleImputer(strategy='most_frequent')),
                            ('encode', OneHotEncoder(handle_unknown='ignore'))])
    return Pipeline([('preprocess', ColumnTransformer([('numeric', numeric, NUMERIC),
                      ('category', categorical, CATEGORICAL)])), ('classifier', classifier)])


def metrics(y, probability, threshold):
    prediction = (probability >= threshold).astype(int)
    return {'precision': float(precision_score(y, prediction, zero_division=0)),
            'recall': float(recall_score(y, prediction, zero_division=0)),
            'f1': float(f1_score(y, prediction, zero_division=0)),
            'roc_auc': float(roc_auc_score(y, probability)),
            'average_precision': float(average_precision_score(y, probability)),
            'confusion_matrix': confusion_matrix(y, prediction, labels=[0, 1]).tolist()}


def train(url=None):
    df = load_performance(url)
    train_df, validation, test, validation_start, test_start = chronological_split(df)
    candidates = {'dummy': DummyClassifier(strategy='prior'),
                  'logistic_regression': LogisticRegression(max_iter=1500, random_state=42),
                  'random_forest': RandomForestClassifier(n_estimators=160, max_depth=12,
                                                         min_samples_leaf=12, random_state=42, n_jobs=-1)}
    fitted, results = {}, {}
    for name, classifier in candidates.items():
        model = pipeline(classifier)
        model.fit(features(train_df), train_df.is_delayed.astype(int))
        probability = model.predict_proba(features(validation))[:, 1]
        threshold = max(np.linspace(.15, .75, 25), key=lambda t: f1_score(validation.is_delayed, probability >= t, zero_division=0))
        results[name] = {'threshold': float(threshold), **metrics(validation.is_delayed, probability, threshold)}
        fitted[name] = model
    selected = max(results, key=lambda name: results[name]['f1'])
    threshold = results[selected]['threshold']
    model = fitted[selected]
    test_probability = model.predict_proba(features(test))[:, 1]
    evaluated = metrics(test.is_delayed, test_probability, threshold)
    manifest_bytes = (ROOT/'data/raw/manifest.json').read_bytes()
    version = f"{selected}-{hashlib.sha256(manifest_bytes).hexdigest()[:10]}"
    bundle = {'pipeline': model, 'threshold': threshold, 'model_version': version,
              'features': NUMERIC+CATEGORICAL, 'trained_before': str(validation_start)}
    joblib.dump(bundle, ROOT/'models/delay_model.joblib')
    report = {'synthetic': True, 'selected_model': selected, 'model_version': version,
              'threshold': threshold, 'validation_candidates': results, 'test_metrics': evaluated,
              'split_rows': {'train': len(train_df), 'validation': len(validation), 'test': len(test)},
              'validation_start': str(validation_start), 'test_start': str(test_start),
              'selection': 'Highest validation F1 after validation-only threshold tuning; one test evaluation.',
              'limitations': 'Synthetic data. Delivered-only test outcomes exclude unresolved shipments; recent cohorts are censored. Model scores are not calibrated operational probabilities.'}
    (ROOT/'reports/model_metrics.json').write_text(json.dumps(report, indent=2))
    rows = []
    for name, result in results.items():
        rows.append({'model': name, 'split': 'validation', **{k:v for k,v in result.items() if k != 'confusion_matrix'}})
    rows.append({'model': selected, 'split': 'test', 'threshold': threshold,
                 **{k:v for k,v in evaluated.items() if k != 'confusion_matrix'}})
    pd.DataFrame(rows).to_csv(ROOT/'data/processed/model_metrics.csv', index=False)
    predictions = test[['shipment_id', 'dispatch_at', 'is_delayed']].copy()
    predictions['delay_probability'] = test_probability
    predictions['predicted_delayed'] = (test_probability >= threshold).astype(int)
    predictions.to_csv(ROOT/'data/processed/test_predictions.csv', index=False)
    # Score only shipments dispatched after the training cutoff, excluding cancelled ones.
    scoring = df[(df.dispatch_at >= validation_start) & df.status.ne('Cancelled')]
    scored = pd.DataFrame({'shipment_id': scoring.shipment_id,
                           'model_version': version,
                           'delay_probability': model.predict_proba(features(scoring))[:, 1]})
    scored['predicted_delayed'] = (scored.delay_probability >= threshold).astype(int)
    scored['threshold'] = threshold
    scored['scored_at'] = utc_now()
    scored.to_csv(ROOT/'data/processed/shipment_predictions.csv', index=False)
    engine = engine_for(url)
    with engine.begin() as conn:
        upsert(conn, 'shipment_predictions', scored)
    engine.dispose()
    lines = [f'# Delay model evaluation\n\nSynthetic data. Selected model: **{selected}**.',
             f'Threshold: {threshold:.2f}. Train / validation / test rows: {len(train_df)} / {len(validation)} / {len(test)}.',
             '\n| Test metric | Value |\n|---|---|']
    lines += [f'| {k} | {v:.4f} |' for k,v in evaluated.items() if k != 'confusion_matrix']
    lines += [f'\nConfusion matrix (actual rows, predicted columns; on-time then delayed): `{evaluated["confusion_matrix"]}`.',
              '\nOnly dispatch-time features are used. Training outcomes must be known before validation starts; validation outcomes must be known before testing starts.',
              '\n'+report['limitations']]
    (ROOT/'reports/model_report.md').write_text('\n\n'.join(lines), encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(train(), indent=2))
