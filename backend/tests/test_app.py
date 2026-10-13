from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from app.services.data_service import inspect_csv_file, load_solar_dataset, preprocess_dataset, validate_csv_file
from app.database.repository import SQLiteRepository
from app.services.ml_service import engineer_features, predict_anomalies, train_anomaly_model
from app.services.alert_service import generate_alerts

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / 'backend' / 'data' / 'raw' / 'Plant_1_Generation_Data.csv'
PROCESSED_PATH = ROOT / 'backend' / 'data' / 'processed' / 'demo_processed.parquet'


def test_health_endpoint():
    response = client.get('/api/health')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert body['storage_backend'] in ('mongodb_atlas', 'sqlite_fallback')


def test_model_training_rejects_invalid_contamination():
    response = client.post('/api/ml/train', json={'contamination': 0.9})

    assert response.status_code == 422


def test_dashboard_summary_uses_real_dataset_counts_and_dates():
    response = client.get('/api/dashboard/summary')

    assert response.status_code == 200
    summary = response.json()
    assert summary['total_plants'] == 2
    assert summary['total_equipment'] == 44
    assert summary['data_freshness'].startswith('2020-06-17')
    assert summary['latest_power_kw'] == 0
    assert summary['latest_irradiance_w_m2'] == 0
    assert summary['avg_health_score'] is None or 0 <= summary['avg_health_score'] <= 100
    assert summary['energy_generation_source_units'] > 0
    assert summary['energy_generation_unit'] == 'source unit not declared'


def test_dataset_inspection_works():
    result = inspect_csv_file(str(DATASET_PATH))
    assert 'filename' in result
    assert 'row_count' in result
    assert 'column_count' in result
    assert 'timestamp_min' in result or 'timestamp_max' in result


def test_preprocessing_produces_valid_dataframe():
    df = preprocess_dataset(str(DATASET_PATH), str(PROCESSED_PATH))
    assert 'timestamp' in df.columns
    assert 'power_kw' in df.columns
    assert 'ac_power' in df.columns
    assert 'date_time' in df.columns
    assert len(df) > 0


def test_csv_validation_passes_for_demo_data():
    result = validate_csv_file(str(DATASET_PATH))
    assert result['valid'] is True
    assert result['row_count'] > 0


def test_upload_rejects_csv_without_timestamp():
    response = client.post('/api/data/upload', files={'file': ('invalid.csv', b'foo,bar\n1,2\n', 'text/csv')})

    assert response.status_code == 422
    assert 'timestamp' in response.json()['detail'].lower()


def test_timestamp_parsing_and_missing_summary():
    result = inspect_csv_file(str(DATASET_PATH))
    assert result['timestamp_min'] is not None
    assert result['timestamp_max'] is not None
    assert sum(result['missing_values'].values()) >= 0
    assert result['verified_failure_labels_exist'] is False


def test_related_weather_join_preserves_generation_row_count():
    generation = load_solar_dataset(str(DATASET_PATH))
    assert generation.height == 136476
    assert 'temperature_c' in generation.columns
    assert 'ambient_temperature_c' in generation.columns
    assert 'irradiance_w_m2' in generation.columns
    assert generation['irradiance_w_m2'].null_count() < generation.height


def test_alert_generation_api():
    response = client.get('/api/alerts')
    assert response.status_code == 200
    payload = response.json()
    assert 'items' in payload or 'alerts' in payload


def test_alerts_and_maintenance_persist_between_local_repository_instances(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'data_dir', str(tmp_path))
    first_store = SQLiteRepository()
    alert = first_store.create_alerts([{'alert_id': 'ALT-PERSIST-1', 'status': 'Open'}])[0]
    maintenance = first_store.create_maintenance({
        'equipment_id': 'INV-TEST',
        'plant_id': 'PLANT-TEST',
        'title': 'Inspect inverter',
        'description': 'Check connectors',
        'status': 'scheduled',
    })
    first_store.update_alert(alert['alert_id'], {'status': 'Acknowledged'})
    first_store.create_alerts([alert])
    first_store.update_maintenance(maintenance['maintenance_id'], {'status': 'completed'})
    first_store.save_predictions([
        {'timestamp': '2020-05-15T10:00:00', 'plant_id': 'P1', 'equipment_id': 'INV-1', 'anomaly_score': 0.25, 'anomaly_label': 1, 'severity': 'Medium'},
        {'timestamp': '2020-05-15T10:15:00', 'plant_id': 'P1', 'equipment_id': 'INV-1', 'anomaly_score': 0.75, 'anomaly_label': -1, 'severity': 'Critical'},
    ])

    restarted_store = SQLiteRepository()
    assert restarted_store.get_alert(alert['alert_id'])['status'] == 'Acknowledged'
    assert next(
        record for record in restarted_store.get_maintenance()
        if record['maintenance_id'] == maintenance['maintenance_id']
    )['status'] == 'completed'
    latest_prediction = restarted_store.get_latest_predictions()[0]
    assert latest_prediction['anomaly_score'] == 0.75
    assert latest_prediction['health_score'] == 25.0
    assert restarted_store.get_predictions(anomalies_only=True)[0]['anomaly_label'] == -1


def test_alert_ids_are_stable_and_include_observed_measurements():
    anomaly = {
        'anomaly_label': -1,
        'anomaly_score': 0.91,
        'plant_id': '4135001',
        'equipment_id': 'INV-A',
        'timestamp': '2020-05-15T10:00:00',
        'observed_measurements': {'power_kw': 12.5},
        'feature_deviations': [{'feature': 'power_kw', 'z_score': 2.8}],
    }
    first = generate_alerts([anomaly])[0]
    second = generate_alerts([anomaly])[0]

    assert first['alert_id'] == second['alert_id']
    assert first['observed_measurements'] == {'power_kw': 12.5}
    assert first['feature_deviations'][0]['observed_value'] == 12.5
    assert 'power_kw' in first['explanation']
    assert 'not a confirmed fault' in first['explanation']


def test_anomaly_model_trains_on_raw_generation_dataset():
    result = train_anomaly_model(str(DATASET_PATH))

    assert result['status'] == 'trained'
    assert result['n_training_records'] > 0
    assert 'power_kw' in result['feature_list']
    assert result['anomaly_count'] > 0
    assert 'power_kw_deviation' in result['feature_list']
    assert all(row['anomaly_label'] in (-1, 1) for row in result['results'])
    prediction = predict_anomalies(str(DATASET_PATH))
    assert prediction['status'] == 'predicted'
    assert prediction['prediction_count'] == result['n_training_records']


def test_feature_engineering_uses_equipment_rolling_baseline():
    from datetime import datetime, timedelta
    import polars as pl

    frame = pl.DataFrame({
        'plant_id': ['P1'] * 3,
        'equipment_id': ['INV-1'] * 3,
        'timestamp': [datetime(2020, 1, 1) + timedelta(minutes=15 * step) for step in range(3)],
        'power_kw': [1.0, 2.0, 5.0],
    })

    result = engineer_features(frame)
    assert result['power_kw_deviation'][1] == 0.5
    assert result['power_kw_deviation'][2] > result['power_kw_deviation'][1]


def test_adjacent_anomalies_are_grouped_as_one_event():
    rows = [
        {'anomaly_label': -1, 'anomaly_score': 0.8, 'plant_id': 'P1', 'equipment_id': 'INV-A', 'timestamp': f'2020-05-15T10:{minute:02d}:00', 'observed_measurements': {'power_kw': 10}}
        for minute in (0, 15)
    ]
    alerts = generate_alerts(rows)

    assert len(alerts) == 1
    assert alerts[0]['observations_in_event'] == 2
