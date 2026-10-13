from __future__ import annotations

import argparse
from pathlib import Path

from app.services.ml_service import train_anomaly_model


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train the unsupervised anomaly detection model.')
    parser.add_argument('file_path', nargs='?', default=str(Path(__file__).resolve().parent / 'data' / 'sample' / 'demo_solar_data.csv'))
    args = parser.parse_args()

    result = train_anomaly_model(args.file_path)
    print(f"Model type: {result['model_type']}")
    print(f"Training rows: {result['n_training_records']}")
    print(f"Detected anomalies: {result['anomaly_count']}")
    print(f"Model artifact path: {result['model_path']}")
