from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
import polars as pl
from pyod.models.iforest import IForest
from sklearn.preprocessing import StandardScaler

from app.services.data_service import load_solar_dataset, resolve_primary_dataset_file


DATA_DIR = Path(__file__).resolve().parents[2] / 'data' / 'processed'
DATA_DIR.mkdir(parents=True, exist_ok=True)


def select_feature_columns(df: pl.DataFrame) -> List[str]:
    candidates = [
        'power_kw', 'voltage_v', 'current_a', 'temperature_c', 'ambient_temperature_c', 'irradiance_w_m2', 'humidity_pct', 'wind_speed_m_s', 'energy_kwh',
        'power_kw_deviation', 'power_kw_rolling_std', 'temperature_c_deviation', 'temperature_c_rolling_std',
    ]
    return [col for col in candidates if col in df.columns]


def engineer_features(df: pl.DataFrame) -> pl.DataFrame:
    if not {'equipment_id', 'timestamp'}.issubset(df.columns):
        return df
    grouping = ['plant_id', 'equipment_id'] if 'plant_id' in df.columns else ['equipment_id']
    engineered = df.sort(grouping + ['timestamp'])
    for source, prefix in [('power_kw', 'power_kw'), ('temperature_c', 'temperature_c')]:
        if source not in engineered.columns:
            continue
        rolling_mean = pl.col(source).rolling_mean(window_size=4, min_periods=2).over(grouping)
        rolling_std = pl.col(source).rolling_std(window_size=4, min_periods=2).over(grouping)
        engineered = engineered.with_columns(
            (pl.col(source) - rolling_mean).alias(f'{prefix}_deviation'),
            rolling_std.alias(f'{prefix}_rolling_std'),
        )
    return engineered


def find_feature_deviations(values: np.ndarray, feature_columns: List[str], threshold: float = 2.5) -> List[Dict[str, Any]]:
    return [
        {'feature': feature_columns[index], 'z_score': round(float(score), 2)}
        for index, score in enumerate(values)
        if abs(float(score)) >= threshold
    ]


def prepare_model_frame(df: pl.DataFrame, context_columns: List[str], feature_columns: List[str]):
    frame = df.select(context_columns + feature_columns).clone()
    for column in feature_columns:
        frame = frame.with_columns(pl.col(column).cast(pl.Float64, strict=False))
    frame = frame.drop_nulls(subset=feature_columns)
    excluded_nighttime = 0
    if 'irradiance_w_m2' in feature_columns:
        excluded_nighttime = frame.filter(pl.col('irradiance_w_m2') <= 0).height
        frame = frame.filter(pl.col('irradiance_w_m2') > 0)
    return frame, excluded_nighttime


def train_anomaly_model(file_path: str, contamination: float = 0.08) -> Dict[str, Any]:
    source = Path(file_path)
    df = engineer_features(load_solar_dataset(str(source)))
    feature_columns = select_feature_columns(df)
    if not feature_columns:
        raise ValueError('No supported numeric monitoring columns were found for anomaly detection.')

    context_columns = [column for column in ['timestamp', 'plant_id', 'equipment_id', 'source_key'] if column in df.columns]
    frame, excluded_nighttime = prepare_model_frame(df, context_columns, feature_columns)

    if frame.height == 0:
        raise ValueError('No valid rows remain after removing missing feature values.')

    X = frame.select(feature_columns).to_numpy()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IForest(contamination=contamination, random_state=42, n_estimators=200)
    model.fit(X_scaled)
    raw_scores = np.asarray(model.decision_scores_)
    anomaly_labels = np.where(np.asarray(model.labels_) == 1, -1, 1)

    min_score = float(raw_scores.min())
    max_score = float(raw_scores.max())
    score_span = max(max_score - min_score, 1e-9)
    relative_scores = (raw_scores - min_score) / score_span

    results: List[Dict[str, Any]] = []
    severity_thresholds = np.quantile(relative_scores, [0.75, 0.9])
    context_rows = frame.select(context_columns).to_dicts()
    measurement_rows = frame.select(feature_columns).to_dicts()
    for idx, row in enumerate(context_rows):
        timestamp = row.get('timestamp')
        if timestamp is not None:
            timestamp = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
        results.append({
            'timestamp': timestamp,
            'equipment_id': row.get('equipment_id') or row.get('source_key') or 'UNKNOWN',
            'plant_id': row.get('plant_id', 'UNKNOWN'),
            'anomaly_score': round(float(relative_scores[idx]), 4),
            'health_score': round(max(0.0, min(100.0, 100 * (1 - float(relative_scores[idx])))), 1),
            'anomaly_label': int(anomaly_labels[idx]),
            'severity': 'Critical' if relative_scores[idx] >= severity_thresholds[1] else 'High' if relative_scores[idx] >= severity_thresholds[0] else 'Medium',
            'observed_measurements': {column: float(value) if value is not None else None for column, value in measurement_rows[idx].items()},
            'feature_deviations': find_feature_deviations(X_scaled[idx], feature_columns),
        })

    model_path = DATA_DIR / 'isolation_forest_model.joblib'
    scaler_path = DATA_DIR / 'feature_scaler.joblib'
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    source_files = sorted(df['source_file'].unique().to_list()) if 'source_file' in df.columns else [source.name]
    metadata = {
        'model_type': 'IsolationForest',
        'training_timestamp': datetime.now(timezone.utc).isoformat(),
        'training_dataset': ', '.join(source_files),
        'feature_list': feature_columns,
        'n_training_records': int(frame.height),
        'anomaly_count': int(np.sum(anomaly_labels == -1)),
        'model_status': 'trained',
        'known_limitations': 'Unsupervised anomaly ranking only; scores are normalized within this training run, are not failure probabilities, and the model-relative condition index is not a validated equipment health score. Feature deviations are standardized-value indicators, not causal explanations.',
        'feature_engineering': 'Per-plant/equipment rolling window of four observations: power and module-temperature deviations from the rolling mean and rolling standard deviation; minimum two observations required.',
        'explanation_threshold_z': 2.5,
        'nighttime_filter': 'Records with irradiation <= 0 are excluded from model fitting/scoring because zero irradiation and zero output are normal nighttime operation; raw records remain available in charts and history.',
        'nighttime_records_excluded': excluded_nighttime,
        'health_score_method': 'Model-relative condition index = 100 × (1 − normalized anomaly score); this is not a validated equipment health measure.',
        'contamination': contamination,
        'score_min': min_score,
        'score_max': max_score,
        'severity_thresholds': [float(value) for value in severity_thresholds],
        'source_data': 'simulated demo' if 'demo' in source.name.lower() else 'local historical CSV',
        'source_files': source_files,
    }

    metadata_path = DATA_DIR / 'model_metadata.json'
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return {
        'model_type': metadata['model_type'],
        'training_dataset': metadata['training_dataset'],
        'training_timestamp': metadata['training_timestamp'],
        'feature_list': feature_columns,
        'n_training_records': int(frame.height),
        'anomaly_count': int(metadata['anomaly_count']),
        'contamination': contamination,
        'nighttime_records_excluded': excluded_nighttime,
        'nighttime_filter': metadata['nighttime_filter'],
        'feature_engineering': metadata['feature_engineering'],
        'status': 'trained',
        'results': results,
        'model_path': str(model_path),
        'scaler_path': str(scaler_path),
    }


def predict_anomalies(file_path: str | None = None) -> Dict[str, Any]:
    model_path = DATA_DIR / 'isolation_forest_model.joblib'
    scaler_path = DATA_DIR / 'feature_scaler.joblib'
    metadata_path = DATA_DIR / 'model_metadata.json'
    if not model_path.exists() or not scaler_path.exists() or not metadata_path.exists():
        raise ValueError('Train an anomaly model before requesting predictions.')

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    source = file_path or resolve_primary_dataset_file()
    df = engineer_features(load_solar_dataset(source))
    feature_columns = metadata['feature_list']
    missing_columns = [column for column in feature_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Prediction data is missing trained features: {', '.join(missing_columns)}")

    context_columns = [column for column in ['timestamp', 'plant_id', 'equipment_id', 'source_key'] if column in df.columns]
    frame, excluded_nighttime = prepare_model_frame(df, context_columns, feature_columns)
    if frame.height == 0:
        raise ValueError('No complete records are available for prediction.')

    values = frame.select(feature_columns).to_numpy()
    scaled = scaler.transform(values)
    raw_scores = np.asarray(model.decision_function(scaled))
    outlier_labels = np.asarray(model.predict(scaled))
    score_span = max(float(metadata['score_max']) - float(metadata['score_min']), 1e-9)
    relative_scores = np.clip((raw_scores - float(metadata['score_min'])) / score_span, 0.0, 1.0)
    thresholds = metadata.get('severity_thresholds', [0.75, 0.9])

    results = []
    context_rows = frame.select(context_columns).to_dicts()
    measurement_rows = frame.select(feature_columns).to_dicts()
    for index, row in enumerate(context_rows):
        timestamp = row.get('timestamp')
        if timestamp is not None:
            timestamp = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
        results.append({
            'timestamp': timestamp,
            'equipment_id': row.get('equipment_id') or row.get('source_key') or 'UNKNOWN',
            'plant_id': row.get('plant_id', 'UNKNOWN'),
            'anomaly_score': round(float(relative_scores[index]), 4),
            'health_score': round(max(0.0, min(100.0, 100 * (1 - float(relative_scores[index])))), 1),
            'anomaly_label': -1 if outlier_labels[index] == 1 else 1,
            'severity': 'Critical' if relative_scores[index] >= thresholds[1] else 'High' if relative_scores[index] >= thresholds[0] else 'Medium',
            'observed_measurements': {column: float(value) if value is not None else None for column, value in measurement_rows[index].items()},
            'feature_deviations': find_feature_deviations(scaled[index], feature_columns, metadata.get('explanation_threshold_z', 2.5)),
        })
    return {
        'status': 'predicted',
        'training_dataset': metadata.get('training_dataset'),
        'training_timestamp': metadata.get('training_timestamp'),
        'feature_list': feature_columns,
        'prediction_count': len(results),
        'anomaly_count': sum(row['anomaly_label'] == -1 for row in results),
        'nighttime_records_excluded': excluded_nighttime,
        'results': results,
    }

def load_trained_model() -> Dict[str, Any]:
    model_path = DATA_DIR / 'isolation_forest_model.joblib'
    scaler_path = DATA_DIR / 'feature_scaler.joblib'
    metadata_path = DATA_DIR / 'model_metadata.json'

    if not model_path.exists() or not scaler_path.exists() or not metadata_path.exists():
        return {'status': 'not_trained', 'model_type': 'IsolationForest', 'feature_list': []}

    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    return {
        'status': metadata.get('model_status', 'trained'),
        'model_type': metadata.get('model_type', 'IsolationForest'),
        'feature_list': metadata.get('feature_list', []),
        'training_dataset': metadata.get('training_dataset'),
        'training_timestamp': metadata.get('training_timestamp'),
        'n_training_records': metadata.get('n_training_records', 0),
        'anomaly_count': metadata.get('anomaly_count', 0),
        'contamination': metadata.get('contamination'),
        'nighttime_records_excluded': metadata.get('nighttime_records_excluded', 0),
        'nighttime_filter': metadata.get('nighttime_filter'),
        'health_score_method': metadata.get('health_score_method'),
        'feature_engineering': metadata.get('feature_engineering'),
        'explanation_threshold_z': metadata.get('explanation_threshold_z'),
        'known_limitations': metadata.get('known_limitations'),
        'model_path': str(model_path),
        'scaler_path': str(scaler_path),
    }
