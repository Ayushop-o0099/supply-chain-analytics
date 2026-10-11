"""Score CSV containing dispatch-time fields, including distance_km."""
import argparse
from pathlib import Path
import joblib
import pandas as pd
from .config import ROOT
from .model import features


def predict(input_path, output_path):
    bundle = joblib.load(ROOT/'models/delay_model.joblib')
    df = pd.read_csv(input_path)
    probability = bundle['pipeline'].predict_proba(features(df))[:, 1]
    output = df.copy()
    output['delay_probability'] = probability
    output['predicted_delayed'] = (probability >= bundle['threshold']).astype(int)
    output['model_version'] = bundle['model_version']
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_csv')
    parser.add_argument('output_csv')
    args = parser.parse_args()
    predict(args.input_csv, args.output_csv)
    print(f'Predictions saved to {args.output_csv}')
