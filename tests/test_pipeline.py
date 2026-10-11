import json
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from src.config import ROOT, AS_OF
from src.validation import validate_shipments, validate_events, validate_dimensions
from src.database import engine_for, metadata, upsert, create_views
from src.analytics import summarize
from src.model import features, chronological_split


@pytest.fixture
def raw():
    return {name: pd.read_csv(ROOT/'data/raw'/f'{name}.csv') for name in
            ['carriers', 'ports', 'routes', 'shipments', 'shipment_events']}


def test_seeded_quality_counts_and_unknown_outcomes(raw):
    good, bad = validate_shipments(raw['shipments'], raw['carriers'], raw['routes'], AS_OF)
    manifest = json.loads((ROOT/'data/raw/manifest.json').read_text())
    assert len(good) == manifest['valid_shipments']
    assert len(bad) == 100
    assert good.shipment_id.is_unique
    assert good.loc[good.status != 'Delivered', 'actual_delivery_at'].isna().all()
    assert len(bad[bad.rejection_reason.str.contains('duplicate')]) == 20


def test_validation_rejects_missing_nonfinite_and_bad_status(raw):
    sample = raw['shipments'].iloc[:5].copy()
    sample['carrier_id'] = sample.carrier_id.astype(float)
    sample.loc[0, 'dispatch_at'] = 'not-a-date'
    sample.loc[1, 'weight_kg'] = np.inf
    sample.loc[2, 'status'] = 'Unknown'
    sample.loc[3, 'shipment_id'] = None
    sample.loc[4, 'carrier_id'] = 1.5
    good, bad = validate_shipments(sample, raw['carriers'], raw['routes'], AS_OF)
    assert len(good) == 0
    assert len(bad) == 5


def test_missing_required_column_fails(raw):
    with pytest.raises(ValueError, match='Missing shipment columns'):
        validate_shipments(raw['shipments'].drop(columns='status'), raw['carriers'], raw['routes'], AS_OF)


def test_dimension_reference_guard(raw):
    raw['routes'].loc[0, 'origin_port_id'] = 999
    with pytest.raises(ValueError, match='unknown port'):
        validate_dimensions(raw)


def test_event_reference_and_time_guard(raw):
    good, _ = validate_shipments(raw['shipments'], raw['carriers'], raw['routes'], AS_OF)
    sample = raw['shipment_events'].iloc[:3].copy()
    sample.loc[0, 'shipment_id'] = 'missing'
    sample.loc[1, 'event_at'] = '2023-01-01'
    sample.loc[2, 'port_id'] = 999
    valid, rejected = validate_events(sample, good, raw['ports'], AS_OF)
    assert valid.empty
    assert len(rejected) == 3


def test_idempotent_upsert_updates_and_foreign_keys(tmp_path, raw):
    engine = engine_for(f'sqlite:///{(tmp_path / "test.db").as_posix()}')
    metadata.create_all(engine)
    good, _ = validate_shipments(raw['shipments'], raw['carriers'], raw['routes'], AS_OF)
    sample = good.head(10).copy()
    with engine.begin() as conn:
        for name in ['carriers', 'ports', 'routes']:
            upsert(conn, name, raw[name])
        upsert(conn, 'shipments', sample)
        sample.loc[sample.index[0], 'shipping_cost_usd'] = 123.45
        upsert(conn, 'shipments', sample)
        assert conn.execute(text('SELECT COUNT(*) FROM shipments')).scalar() == 10
        assert conn.execute(text('SELECT shipping_cost_usd FROM shipments ORDER BY shipment_id LIMIT 1')).scalar() == pytest.approx(123.45)
        create_views(conn)
        rows = pd.read_sql(text('SELECT * FROM vw_shipment_performance'), conn)
        expected = (sample.actual_delivery_at > sample.promised_delivery_at).astype(int)
        assert rows.is_delayed.tolist() == expected.tolist()
    invalid = sample.head(1).copy()
    invalid['carrier_id'] = 999
    with pytest.raises(IntegrityError), engine.begin() as conn:
        upsert(conn, 'shipments', invalid)
    engine.dispose()


def test_kpi_boundary_and_empty_selection():
    frame = pd.DataFrame({
        'status': ['Delivered','Delivered','In Transit','Cancelled'],
        'is_delayed': [0,1,np.nan,np.nan], 'delay_hours':[0,2,np.nan,np.nan],
        'promised_delivery_at':pd.to_datetime(['2025-01-01']*4), 'shipping_cost_usd':[100]*4})
    result = summarize(frame, AS_OF)
    assert result['on_time_rate'] == .5
    assert result['mean_delay_hours_delivered'] == 1
    assert result['overdue_open'] == 1
    assert summarize(frame.iloc[0:0], AS_OF)['on_time_rate'] is None


def test_exact_promise_and_open_outcome_in_sql(tmp_path, raw):
    engine = engine_for(f'sqlite:///{(tmp_path / "boundary.db").as_posix()}')
    metadata.create_all(engine)
    good, _ = validate_shipments(raw['shipments'], raw['carriers'], raw['routes'], AS_OF)
    sample = good.head(2).copy()
    sample.loc[sample.index[0], 'actual_delivery_at'] = sample.iloc[0].promised_delivery_at
    sample.loc[sample.index[1], 'status'] = 'In Transit'
    sample.loc[sample.index[1], 'actual_delivery_at'] = pd.NaT
    with engine.begin() as conn:
        for name in ['carriers','ports','routes']:
            upsert(conn,name,raw[name])
        upsert(conn,'shipments',sample)
        create_views(conn)
        rows = conn.execute(text('SELECT is_delayed,delay_hours FROM vw_shipment_performance ORDER BY shipment_id')).all()
        assert rows[0] == (0, 0)
        assert rows[1] == (None, None)
    engine.dispose()


def test_model_features_ignore_post_dispatch_information():
    frame = pd.read_csv(ROOT/'data/processed/shipment_performance.csv').head(10)
    before = features(frame)
    frame['actual_delivery_at'] = '2099-01-01'
    frame['is_delayed'] = 1
    frame['status'] = 'Cancelled'
    pd.testing.assert_frame_equal(before, features(frame))


def test_temporal_splits_guard_label_availability():
    frame = pd.read_csv(ROOT/'data/processed/shipment_performance.csv',
                        parse_dates=['dispatch_at','actual_delivery_at','promised_delivery_at'])
    train, validation, test, val_start, test_start = chronological_split(frame)
    assert train.actual_delivery_at.max() < val_start
    assert validation.actual_delivery_at.max() < test_start
    assert train.dispatch_at.max() < validation.dispatch_at.min()
    assert validation.dispatch_at.max() < test.dispatch_at.min()
    assert not set(train.shipment_id) & set(test.shipment_id)


def test_prediction_artifact_and_export():
    import joblib
    model = joblib.load(ROOT/'models/delay_model.joblib')
    frame = pd.read_csv(ROOT/'data/processed/shipment_performance.csv').head(3)
    probability = model['pipeline'].predict_proba(features(frame))[:,1]
    assert np.isfinite(probability).all()
    assert ((probability>=0)&(probability<=1)).all()
    predictions = pd.read_csv(ROOT/'data/processed/shipment_predictions.csv')
    assert predictions.shipment_id.is_unique
    assert predictions.delay_probability.between(0,1).all()
