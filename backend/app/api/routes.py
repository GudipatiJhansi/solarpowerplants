from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

import polars as pl
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import logger
from app.database.repository import DataStore
from app.schemas.models import AlertUpdateRequest, HealthResponse, MaintenanceRecordRequest, MaintenanceRecordUpdateRequest, ModelPredictionRequest, ModelTrainingRequest
from app.services.alert_service import generate_alerts
from app.services.data_service import inspect_csv_file, list_dataset_files, load_dataset_summary, load_solar_dataset, preprocess_dataset, resolve_primary_dataset_file, validate_csv_file
from app.services.ml_service import load_trained_model, predict_anomalies, train_anomaly_model

router = APIRouter()
store = DataStore()


@lru_cache(maxsize=1)
def load_generation_data() -> pl.DataFrame:
    return load_solar_dataset()


@router.get('/health')
def health() -> HealthResponse:
    logger.info('Health endpoint requested')
    primary_path = Path(resolve_primary_dataset_file())
    is_demo = 'sample' in primary_path.parts or 'demo' in primary_path.name.lower()
    return HealthResponse(
        status='ok',
        message='Solar predictive maintenance backend is running.',
        data_source='simulated demo CSV' if is_demo else 'local historical solar CSV',
        demo_mode=is_demo,
        storage_backend=store.storage_backend,
    )


@router.get('/dashboard/summary')
def dashboard_summary():
    df = load_generation_data()
    alerts = store.get_alerts()
    latest_predictions = store.get_latest_predictions()
    health_values = [float(item['health_score']) for item in latest_predictions if item.get('health_score') is not None]
    severity_counts = {severity: sum(item.get('severity') == severity for item in alerts) for severity in ['Critical', 'High', 'Medium', 'Low']}
    if df.is_empty():
        return {
            'total_plants': 0, 'total_equipment': 0, 'latest_power_kw': None,
            'avg_health_score': round(sum(health_values) / len(health_values), 1) if health_values else None,
            'active_alerts': sum(item.get('status') != 'Resolved' for item in alerts),
            'critical_alerts': sum(item.get('severity') == 'Critical' and item.get('status') != 'Resolved' for item in alerts),
            'alert_severity_distribution': severity_counts,
            'energy_generation_kwh': None, 'data_source': 'no dataset available',
            'energy_generation_source_units': None,
            'energy_generation_unit': 'source unit not declared',
            'latest_irradiance_w_m2': None,
            'data_freshness': None, 'monitored_period': None,
        }
    latest = df['timestamp'].max()
    latest_rows = df.filter(pl.col('timestamp') == latest)
    plants = df['plant_id'].drop_nulls().n_unique() if 'plant_id' in df.columns else 0
    equipment = df['equipment_id'].drop_nulls().n_unique() if 'equipment_id' in df.columns else 0
    energy_generation_source_units = None
    if {'daily_yield', 'plant_id', 'equipment_id', 'timestamp'}.issubset(df.columns):
        per_inverter_day = (
            df.with_columns(pl.col('timestamp').dt.date().alias('_date'))
            .group_by(['plant_id', 'equipment_id', '_date'])
            .agg(pl.col('daily_yield').max().alias('daily_total'))
        )
        energy_generation_source_units = float(per_inverter_day['daily_total'].sum())
    return {
        'total_plants': plants,
        'total_equipment': equipment,
        'latest_power_kw': round(float(latest_rows['power_kw'].sum()), 3) if 'power_kw' in latest_rows.columns else None,
        'latest_irradiance_w_m2': round(float(latest_rows['irradiance_w_m2'].mean()), 6) if 'irradiance_w_m2' in latest_rows.columns and latest_rows['irradiance_w_m2'].null_count() < latest_rows.height else None,
        'avg_health_score': round(sum(health_values) / len(health_values), 1) if health_values else None,
        'health_score_method': '100 × (1 − normalized anomaly score); relative model index, not a validated health measure.' if health_values else None,
        'active_alerts': sum(item.get('status') != 'Resolved' for item in alerts),
        'critical_alerts': sum(item.get('severity') == 'Critical' and item.get('status') != 'Resolved' for item in alerts),
        'alert_severity_distribution': severity_counts,
        'energy_generation_kwh': None,
        'energy_generation_source_units': round(energy_generation_source_units, 2) if energy_generation_source_units is not None else None,
        'energy_generation_unit': 'source unit not declared' if energy_generation_source_units is not None else None,
        'data_source': 'local historical solar CSV',
        'data_freshness': latest.isoformat() if latest is not None else None,
        'monitored_period': f"{df['timestamp'].min().date()} to {latest.date()}" if latest is not None else None,
    }


@router.get('/dashboard/trends')
def dashboard_trends():
    df = load_generation_data()
    if df.is_empty() or 'timestamp' not in df.columns:
        return {'timestamps': [], 'power': [], 'temperature': [], 'irradiance': [], 'available_metrics': []}
    interval = max(1, df.height // 2000)
    selected = df.sort('timestamp').gather_every(interval)
    prediction_rows = list(reversed(store.get_predictions(limit=2000, chart_samples_only=True)))
    available_metrics = ['power_kw']
    if 'temperature_c' in selected.columns:
        available_metrics.append('temperature_c')
    if 'irradiance_w_m2' in selected.columns:
        available_metrics.append('irradiance_w_m2')
    return {
        'timestamps': [value.isoformat() if value is not None else None for value in selected['timestamp'].to_list()],
        'power': selected['power_kw'].to_list() if 'power_kw' in selected.columns else [],
        'temperature': selected['temperature_c'].to_list() if 'temperature_c' in selected.columns else [],
        'irradiance': selected['irradiance_w_m2'].to_list() if 'irradiance_w_m2' in selected.columns else [],
        'available_metrics': available_metrics,
        'prediction_timestamps': [item.get('timestamp') for item in prediction_rows],
        'anomaly_scores': [item.get('anomaly_score') for item in prediction_rows],
        'condition_scores': [item.get('health_score') for item in prediction_rows],
    }


@router.get('/plants')
def get_plants():
    df = load_generation_data()
    if df.is_empty() or 'plant_id' not in df.columns:
        return []
    return [{'plant_id': str(value), 'name': f'Plant {value}', 'location': 'Not provided in dataset'} for value in df['plant_id'].drop_nulls().unique().sort().to_list()]


@router.get('/equipment')
def get_equipment():
    df = load_generation_data()
    if df.is_empty() or 'equipment_id' not in df.columns:
        return []
    latest = df.sort('timestamp').group_by('equipment_id', maintain_order=True).last()
    latest_predictions = {item.get('equipment_id'): item for item in store.get_latest_predictions()}
    output = []
    for row in latest.to_dicts():
        prediction = latest_predictions.get(str(row.get('equipment_id')))
        output.append({
            'equipment_id': row.get('equipment_id'),
            'plant_id': str(row.get('plant_id')) if row.get('plant_id') is not None else None,
            'latest_power_kw': row.get('power_kw'),
            'latest_temperature_c': row.get('temperature_c'),
            'health_score': prediction.get('health_score') if prediction else None,
            'health_score_method': 'model-relative condition index; not a validated health measure' if prediction else None,
            'latest_anomaly_score': prediction.get('anomaly_score') if prediction else None,
            'anomaly_status': 'anomaly' if prediction and prediction.get('anomaly_label') == -1 else 'normal' if prediction else 'unscored',
            'risk_indicator': prediction.get('severity', 'not scored') if prediction else 'run model predictions',
            'last_recorded_at': row.get('timestamp').isoformat() if row.get('timestamp') is not None else None,
        })
    return output


@router.get('/equipment/{equipment_id}')
def get_equipment_by_id(equipment_id: str):
    items = get_equipment()
    for item in items:
        if item['equipment_id'] == equipment_id:
            return item
    raise HTTPException(status_code=404, detail='Equipment not found')


@router.get('/equipment/{equipment_id}/history')
def get_equipment_history(equipment_id: str):
    df = load_generation_data()
    if df.is_empty() or 'equipment_id' not in df.columns:
        return {'equipment_id': equipment_id, 'records': []}
    filtered = df.filter(pl.col('equipment_id').cast(pl.String) == equipment_id)
    return {'equipment_id': equipment_id, 'records': filtered.to_dicts()}


@router.post('/data/upload')
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail='No file selected.')
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail='Only CSV uploads are supported.')

    saved_name = Path(file.filename).name
    raw_dir = Path(__file__).resolve().parents[2] / 'data' / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    total_bytes = 0
    while chunk := await file.read(1024 * 1024):
        total_bytes += len(chunk)
        if total_bytes > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail='File size exceeds the 50 MB limit.')
        chunks.append(chunk)
    content = b''.join(chunks)
    if not content:
        raise HTTPException(status_code=422, detail='CSV file is empty.')
    temporary = raw_dir / f'.{uuid.uuid4().hex}.upload.csv'
    temporary.write_bytes(content)
    validation = validate_csv_file(str(temporary))
    if not validation['valid']:
        temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=validation['errors'])
    inspection = inspect_csv_file(str(temporary))
    if inspection['timestamp_column'] is None:
        temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail='CSV must include a recognizable timestamp column.')

    destination = raw_dir / saved_name
    if destination.exists():
        destination = raw_dir / f'{destination.stem}_{uuid.uuid4().hex[:8]}{destination.suffix}'
    temporary.replace(destination)
    load_generation_data.cache_clear()
    inspection['filename'] = destination.name
    dataset_info = {
        'dataset_id': destination.stem,
        'filename': destination.name,
        'source': 'uploaded',
        'data_source': 'uploaded',
        'file_size_bytes': destination.stat().st_size,
        'row_count': inspection['row_count'],
        'column_count': inspection['column_count'],
        'date_start': inspection['timestamp_min'],
        'date_end': inspection['timestamp_max'],
        'status': 'available',
        'quality': 'good',
        'preprocessing_status': 'pending',
        'warnings': inspection['warnings'],
        'errors': inspection['errors'],
    }
    return {'message': 'Dataset uploaded successfully.', 'dataset': dataset_info}


@router.get('/data/datasets')
def list_datasets():
    items = load_dataset_summary()
    repo_items = store.list_datasets()
    return {'items': items + repo_items, 'count': len(items) + len(repo_items)}


@router.get('/data/datasets/{dataset_id}')
def get_dataset(dataset_id: str):
    for item in load_dataset_summary():
        if item['dataset_id'] == dataset_id:
            return item
    for item in store.list_datasets():
        if item['dataset_id'] == dataset_id:
            return item
    raise HTTPException(status_code=404, detail='Dataset not found')


@router.post('/data/inspect')
def inspect_dataset(payload: dict):
    file_path = payload.get('file_path')
    if not file_path:
        raise HTTPException(status_code=400, detail='file_path is required.')
    validation = validate_csv_file(file_path)
    if not validation['valid']:
        return {'valid': False, 'errors': validation['errors'], 'warnings': validation['warnings']}
    inspection = inspect_csv_file(file_path)
    return {'valid': True, 'inspection': inspection}


@router.post('/data/preprocess')
def preprocess_dataset_route(payload: dict):
    file_path = payload.get('file_path')
    output_path = payload.get('output_path') or str(Path(__file__).resolve().parents[2] / 'data' / 'processed' / 'demo_processed.parquet')
    if not file_path:
        raise HTTPException(status_code=400, detail='file_path is required.')
    df = preprocess_dataset(file_path, output_path)
    return {'message': 'Preprocessing completed.', 'rows': int(df.height), 'columns': list(df.columns), 'output_path': output_path}


@router.post('/ml/train')
def train_model(payload: ModelTrainingRequest):
    file_path = payload.file_path or resolve_primary_dataset_file()
    result = train_anomaly_model(file_path, contamination=payload.contamination)
    store.set_model_metadata({
        'model_type': result['model_type'],
        'training_dataset': result['training_dataset'],
        'training_timestamp': result['training_timestamp'],
        'feature_list': result['feature_list'],
        'n_training_records': result['n_training_records'],
        'anomaly_count': result['anomaly_count'],
        'status': result['status'],
        'model_path': result['model_path'],
        'known_limitations': 'Unsupervised anomaly ranking only; no verified failure labels or validated failure probabilities.',
        'health_score_method': '100 × (1 − normalized anomaly score); model-relative condition index, not a validated equipment-health measure.',
        'contamination': payload.contamination,
        'nighttime_records_excluded': result['nighttime_records_excluded'],
        'nighttime_filter': result['nighttime_filter'],
        'feature_engineering': result['feature_engineering'],
    })
    store.save_predictions(result['results'])
    return {key: value for key, value in result.items() if key != 'results'}


@router.post('/ml/predict')
def predict(payload: ModelPredictionRequest):
    try:
        model_result = predict_anomalies(payload.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    alerts = generate_alerts(model_result['results'], settings.alert_group_window_minutes)
    alerts = store.create_alerts(alerts)
    store.save_predictions(model_result['results'])
    return {
        'prediction_count': model_result['prediction_count'],
        'anomaly_count': model_result['anomaly_count'],
        'alerts_created_or_existing': len(alerts),
        'nighttime_records_excluded': model_result['nighttime_records_excluded'],
        'alert_group_window_minutes': settings.alert_group_window_minutes,
        'alert_preview': alerts[:10],
        'model_status': model_result['status'],
    }


@router.get('/ml/status')
def ml_status():
    local_metadata = load_trained_model()
    stored_metadata = store.get_model_metadata()
    if stored_metadata.get('status') != 'not_trained' and stored_metadata.get('training_timestamp'):
        return {**local_metadata, **stored_metadata}
    return local_metadata


@router.get('/alerts')
def list_alerts(
    plant_id: Optional[str] = None,
    equipment_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    items = store.get_alerts()
    if plant_id:
        items = [item for item in items if str(item.get('plant_id')) == plant_id]
    if equipment_id:
        items = [item for item in items if str(item.get('equipment_id')) == equipment_id]
    if severity:
        items = [item for item in items if item.get('severity', '').lower() == severity.lower()]
    if status:
        items = [item for item in items if item.get('status', '').lower() == status.lower()]
    if date_from:
        items = [item for item in items if (item.get('timestamp') or '') >= date_from]
    if date_to:
        items = [item for item in items if (item.get('timestamp') or '')[:10] <= date_to]
    total = len(items)
    return {'items': items[offset:offset + limit], 'count': total, 'limit': limit, 'offset': offset}


@router.get('/alerts/{alert_id}')
def get_alert(alert_id: str):
    alert = store.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail='Alert not found')
    return alert


@router.patch('/alerts/{alert_id}')
def update_alert(alert_id: str, payload: AlertUpdateRequest):
    update_data = payload.model_dump(exclude_none=True)
    try:
        alert = store.update_alert(alert_id, update_data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Alert not found') from exc
    return alert


@router.get('/maintenance')
def list_maintenance():
    items = store.get_maintenance()
    return {'items': items, 'count': len(items)}


@router.post('/maintenance')
def create_maintenance(payload: MaintenanceRecordRequest):
    record = payload.model_dump()
    record['created_at'] = datetime.now(timezone.utc).isoformat()
    saved = store.create_maintenance(record)
    return {'message': 'Maintenance record created.', 'record': saved}


@router.patch('/maintenance/{maintenance_id}')
def update_maintenance(maintenance_id: str, payload: MaintenanceRecordUpdateRequest):
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=422, detail='Provide one or more supported maintenance fields.')
    try:
        record = store.update_maintenance(maintenance_id, update_data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Maintenance record not found') from exc
    return {'message': 'Maintenance record updated.', 'record': record}
