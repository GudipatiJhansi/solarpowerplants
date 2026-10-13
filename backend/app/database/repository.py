from __future__ import annotations

import os
import json
import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from pymongo import MongoClient, UpdateOne

from app.core.config import settings


class MemoryRepository:
    def __init__(self):
        base = Path(__file__).resolve().parents[2]
        self.sample_file = base / 'data' / 'sample' / 'demo_solar_data.csv'
        self.datasets: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []
        self.maintenance: List[Dict[str, Any]] = []
        self.predictions: List[Dict[str, Any]] = []
        self.model_metadata: Dict[str, Any] = {}
        self._seed_demo_data()

    def _seed_demo_data(self):
        self.alerts = [
            {
                'alert_id': 'ALT-1001',
                'plant_id': 'PLANT-01',
                'equipment_id': 'INV-01',
                'severity': 'Medium',
                'status': 'Open',
                'timestamp': '2025-01-15T08:15:00Z',
                'anomaly_score': 0.82,
                'explanation': 'Power output deviated from expected trend under moderate irradiance.',
                'recommended_action': 'Inspect inverter cooling and cable connections.',
                'technician': 'A. Singh',
                'observed_measurements': {'power_kw': 42.8, 'temperature_c': 57.2, 'irradiance_w_m2': 600},
            }
        ]
        self.maintenance = [
            {
                'maintenance_id': 'MNT-1001',
                'equipment_id': 'INV-01',
                'plant_id': 'PLANT-01',
                'title': 'Thermal inspection',
                'description': 'Check cable and fan performance after abnormal temperature deviation.',
                'status': 'completed',
                'scheduled_for': '2025-01-16T09:00:00Z',
                'technician': 'A. Singh',
                'resolution_notes': 'No major defect identified; parameter drift corrected.',
            }
        ]

    def get_dashboard_summary(self) -> Dict[str, Any]:
        return {
            'total_plants': 3,
            'total_equipment': 12,
            'latest_power_kw': 183.4,
            'avg_health_score': 86.5,
            'active_alerts': 3,
            'critical_alerts': 1,
            'energy_generation_kwh': 7824.5,
            'data_source': 'simulated demo dataset',
            'data_freshness': '2025-01-15T12:00:00Z',
            'monitored_period': '2024-01-01 to 2025-01-15',
        }

    def get_equipment(self) -> List[Dict[str, Any]]:
        return [
            {
                'equipment_id': 'INV-01',
                'plant_id': 'PLANT-01',
                'latest_power_kw': 71.2,
                'latest_temperature_c': 44.1,
                'health_score': 88.0,
                'anomaly_status': 'watch',
                'risk_indicator': 'medium',
                'last_recorded_at': '2025-01-15T12:00:00Z',
            },
            {
                'equipment_id': 'INV-02',
                'plant_id': 'PLANT-01',
                'latest_power_kw': 79.4,
                'latest_temperature_c': 39.5,
                'health_score': 91.2,
                'anomaly_status': 'normal',
                'risk_indicator': 'low',
                'last_recorded_at': '2025-01-15T12:00:00Z',
            },
            {
                'equipment_id': 'INV-03',
                'plant_id': 'PLANT-02',
                'latest_power_kw': 64.6,
                'latest_temperature_c': 48.7,
                'health_score': 79.6,
                'anomaly_status': 'alert',
                'risk_indicator': 'high',
                'last_recorded_at': '2025-01-15T12:00:00Z',
            },
        ]

    def get_alerts(self) -> List[Dict[str, Any]]:
        return self.alerts

    def get_alert(self, alert_id: str):
        for alert in self.alerts:
            if alert['alert_id'] == alert_id:
                return alert
        return None

    def update_alert(self, alert_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        for alert in self.alerts:
            if alert['alert_id'] == alert_id:
                alert.update(payload)
                return alert
        raise KeyError(f'Alert {alert_id} not found')

    def get_maintenance(self) -> List[Dict[str, Any]]:
        return self.maintenance

    def create_maintenance(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record['maintenance_id'] = record.get('maintenance_id', f"MNT-{len(self.maintenance) + 1000}")
        record['created_at'] = datetime.now(timezone.utc).isoformat()
        self.maintenance.append(record)
        return record

    def list_datasets(self) -> List[Dict[str, Any]]:
        if not self.datasets:
            self.datasets = [
                {
                    'dataset_id': 'demo-solar-2025',
                    'filename': 'demo_solar_data.csv',
                    'source': 'Local sample',
                    'data_source': 'demo',
                    'file_size_bytes': 24500,
                    'row_count': 432,
                    'column_count': 12,
                    'date_start': '2025-01-01T00:00:00Z',
                    'date_end': '2025-01-15T23:30:00Z',
                    'status': 'available',
                    'quality': 'good',
                    'preprocessing_status': 'completed',
                    'warnings': ['Simulated dataset for demonstration only.'],
                    'errors': [],
                }
            ]
        return self.datasets

    def set_model_metadata(self, payload: Dict[str, Any]):
        self.model_metadata = payload
        return self.model_metadata

    def get_model_metadata(self) -> Dict[str, Any]:
        return self.model_metadata or {
            'model_type': 'IsolationForest',
            'status': 'not_trained',
            'training_dataset': 'not available',
            'feature_list': [],
            'n_training_records': 0,
        }


class MongoRepository:
    def __init__(self):
        self.client = None
        self.db = None
        try:
            if settings.mongodb_uri:
                self.client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
                self.db = self.client[settings.mongodb_database]
                self._ensure_indexes()
        except Exception:
            self.client = None
            self.db = None

    def _ensure_indexes(self):
        if self.db is not None:
            self.db.alerts.create_index('alert_id', unique=True)
            self.db.maintenance.create_index('maintenance_id', unique=True)
            self.db.datasets.create_index('dataset_id', unique=True)
            self.db.predictions.create_index('prediction_id', unique=True)
            self.db.predictions.create_index([('is_latest', 1), ('timestamp', -1)])
            self.db.predictions.create_index([('is_chart_sample', 1), ('timestamp', -1)])

    def is_available(self) -> bool:
        if self.db is None:
            return False
        try:
            self.client.admin.command('ping')
            return True
        except Exception:
            return False

    def repository(self):
        if self.is_available():
            return self
        return SQLiteRepository()

    def get_dashboard_summary(self):
        return MemoryRepository().get_dashboard_summary()

    def get_equipment(self):
        return MemoryRepository().get_equipment()

    def get_alerts(self) -> List[Dict[str, Any]]:
        return [self._without_id(item) for item in self.db.alerts.find().sort('_id', -1)]

    def get_alert(self, alert_id: str):
        item = self.db.alerts.find_one({'alert_id': alert_id})
        return self._without_id(item) if item else None

    def create_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records = []
        for alert in alerts:
            record = dict(alert)
            record.setdefault('alert_id', f"ALT-{uuid.uuid4().hex[:10].upper()}")
            records.append(record)
        if records:
            self.db.alerts.bulk_write([
                UpdateOne({'alert_id': record['alert_id']}, {'$setOnInsert': record}, upsert=True)
                for record in records
            ], ordered=False)
            stored = {
                item['alert_id']: self._without_id(item)
                for item in self.db.alerts.find({'alert_id': {'$in': [record['alert_id'] for record in records]}})
            }
            return [stored[record['alert_id']] for record in records if record['alert_id'] in stored]
        return []

    def update_alert(self, alert_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = self.db.alerts.update_one({'alert_id': alert_id}, {'$set': payload})
        if not result.matched_count:
            raise KeyError(f'Alert {alert_id} not found')
        return self.get_alert(alert_id)

    def get_maintenance(self) -> List[Dict[str, Any]]:
        return [self._without_id(item) for item in self.db.maintenance.find().sort('_id', -1)]

    @staticmethod
    def _prepare_predictions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not rows:
            return []
        latest_by_equipment: Dict[tuple[str, str], int] = {}
        for index, row in enumerate(rows):
            key = (str(row.get('plant_id')), str(row.get('equipment_id')))
            current = latest_by_equipment.get(key)
            if current is None or str(row.get('timestamp') or '') > str(rows[current].get('timestamp') or ''):
                latest_by_equipment[key] = index

        sample_step = max(1, len(rows) // 2000)
        retained = {}
        latest_indexes = set(latest_by_equipment.values())
        for index, row in enumerate(rows):
            is_anomaly = row.get('anomaly_label') == -1
            is_chart_sample = index % sample_step == 0
            is_latest = index in latest_indexes
            if not (is_anomaly or is_chart_sample or is_latest):
                continue
            record = dict(row)
            record['plant_id'] = str(record.get('plant_id')) if record.get('plant_id') is not None else None
            record['equipment_id'] = str(record.get('equipment_id')) if record.get('equipment_id') is not None else None
            record['anomaly_score'] = float(record.get('anomaly_score', 0.0))
            record['health_score'] = round(max(0.0, min(100.0, 100 * (1 - record['anomaly_score']))), 1)
            record['is_anomaly'] = is_anomaly
            record['is_chart_sample'] = is_chart_sample
            record['is_latest'] = is_latest
            stable_key = f"{record.get('plant_id')}|{record.get('equipment_id')}|{record.get('timestamp')}"
            record['prediction_id'] = hashlib.sha256(stable_key.encode('utf-8')).hexdigest()
            retained[record['prediction_id']] = record
        return list(retained.values())

    def save_predictions(self, rows: List[Dict[str, Any]]) -> int:
        records = self._prepare_predictions(rows)
        self.db.predictions.update_many({}, {'$set': {'is_latest': False, 'is_chart_sample': False}})
        if records:
            self.db.predictions.bulk_write([
                UpdateOne({'prediction_id': item['prediction_id']}, {'$set': item}, upsert=True)
                for item in records
            ], ordered=False)
        return len(records)

    def get_predictions(self, limit: int = 2000, chart_samples_only: bool = False, anomalies_only: bool = False) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if chart_samples_only:
            query['is_chart_sample'] = True
        if anomalies_only:
            query['is_anomaly'] = True
        return [self._without_id(item) for item in self.db.predictions.find(query).sort('timestamp', -1).limit(limit)]

    def get_latest_predictions(self) -> List[Dict[str, Any]]:
        return [self._without_id(item) for item in self.db.predictions.find({'is_latest': True}).sort('timestamp', -1)]

    def create_maintenance(self, record: Dict[str, Any]) -> Dict[str, Any]:
        saved = dict(record)
        saved.setdefault('maintenance_id', f"MNT-{uuid.uuid4().hex[:10].upper()}")
        saved.setdefault('created_at', datetime.now(timezone.utc).isoformat())
        self.db.maintenance.replace_one({'maintenance_id': saved['maintenance_id']}, saved, upsert=True)
        return saved

    def update_maintenance(self, maintenance_id: str, payload: Dict[str, Any]):
        result = self.db.maintenance.update_one({'maintenance_id': maintenance_id}, {'$set': payload})
        if not result.matched_count:
            raise KeyError(f'Maintenance record {maintenance_id} not found')
        item = self.db.maintenance.find_one({'maintenance_id': maintenance_id})
        return self._without_id(item)

    def list_datasets(self) -> List[Dict[str, Any]]:
        return [self._without_id(item) for item in self.db.datasets.find().sort('_id', -1)]

    def set_model_metadata(self, payload: Dict[str, Any]):
        self.db.app_metadata.replace_one({'_id': 'model_metadata'}, {'_id': 'model_metadata', 'value': payload}, upsert=True)
        return payload

    def get_model_metadata(self) -> Dict[str, Any]:
        item = self.db.app_metadata.find_one({'_id': 'model_metadata'})
        if item:
            return item['value']
        return MemoryRepository().get_model_metadata()

    @staticmethod
    def _without_id(item: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in item.items() if key != '_id'}


class SQLiteRepository(MemoryRepository):
    def __init__(self):
        super().__init__()
        self.alerts = []
        self.maintenance = []
        database_dir = Path(settings.data_dir)
        if not database_dir.is_absolute():
            database_dir = Path(__file__).resolve().parents[2] / database_dir
        database_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = database_dir / 'app_state.sqlite3'
        with sqlite3.connect(self.database_path) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS alerts (alert_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS maintenance (maintenance_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS predictions (prediction_id TEXT PRIMARY KEY, timestamp TEXT, is_anomaly INTEGER, is_chart_sample INTEGER, is_latest INTEGER, payload TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS app_metadata (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def list_datasets(self) -> List[Dict[str, Any]]:
        return []

    def _get_records(self, table: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(f'SELECT payload FROM {table} ORDER BY rowid DESC').fetchall()
        return [json.loads(row[0]) for row in rows]

    def _save_record(self, table: str, key: str, record: Dict[str, Any]):
        key_column = 'alert_id' if table == 'alerts' else 'maintenance_id'
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                f'INSERT INTO {table} ({key_column}, payload) VALUES (?, ?) '
                f'ON CONFLICT({key_column}) DO UPDATE SET payload = excluded.payload',
                (record[key_column], json.dumps(record, default=str)),
            )
        return record

    def get_alerts(self) -> List[Dict[str, Any]]:
        return self._get_records('alerts')

    def get_alert(self, alert_id: str):
        return next((item for item in self.get_alerts() if item['alert_id'] == alert_id), None)

    def create_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records = []
        for alert in alerts:
            record = dict(alert)
            record.setdefault('alert_id', f"ALT-{uuid.uuid4().hex[:10].upper()}")
            records.append(record)
        if not records:
            return []
        with sqlite3.connect(self.database_path) as connection:
            connection.executemany(
                'INSERT OR IGNORE INTO alerts (alert_id, payload) VALUES (?, ?)',
                [(record['alert_id'], json.dumps(record, default=str)) for record in records],
            )
            rows = connection.execute(
                f"SELECT alert_id, payload FROM alerts WHERE alert_id IN ({','.join('?' for _ in records)})",
                [record['alert_id'] for record in records],
            ).fetchall()
        stored = {alert_id: json.loads(payload) for alert_id, payload in rows}
        return [stored[record['alert_id']] for record in records if record['alert_id'] in stored]

    def update_alert(self, alert_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        alert = self.get_alert(alert_id)
        if alert is None:
            raise KeyError(f'Alert {alert_id} not found')
        alert.update(payload)
        return self._save_record('alerts', 'alert_id', alert)

    def get_maintenance(self) -> List[Dict[str, Any]]:
        return self._get_records('maintenance')

    def save_predictions(self, rows: List[Dict[str, Any]]) -> int:
        records = MongoRepository._prepare_predictions(rows)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute('UPDATE predictions SET is_latest = 0, is_chart_sample = 0')
            connection.executemany(
                'INSERT INTO predictions (prediction_id, timestamp, is_anomaly, is_chart_sample, is_latest, payload) '
                'VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(prediction_id) DO UPDATE SET '
                'timestamp=excluded.timestamp, is_anomaly=excluded.is_anomaly, '
                'is_chart_sample=excluded.is_chart_sample, is_latest=excluded.is_latest, payload=excluded.payload',
                [(
                    item['prediction_id'], item.get('timestamp'), int(item['is_anomaly']),
                    int(item['is_chart_sample']), int(item['is_latest']), json.dumps(item, default=str),
                ) for item in records],
            )
        return len(records)

    def get_predictions(self, limit: int = 2000, chart_samples_only: bool = False, anomalies_only: bool = False) -> List[Dict[str, Any]]:
        query = 'SELECT payload FROM predictions WHERE 1=1'
        parameters = []
        if chart_samples_only:
            query += ' AND is_chart_sample = 1'
        if anomalies_only:
            query += ' AND is_anomaly = 1'
        query += ' ORDER BY timestamp DESC LIMIT ?'
        parameters.append(limit)
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_latest_predictions(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute('SELECT payload FROM predictions WHERE is_latest = 1 ORDER BY timestamp DESC').fetchall()
        return [json.loads(row[0]) for row in rows]

    def create_maintenance(self, record: Dict[str, Any]) -> Dict[str, Any]:
        saved = dict(record)
        saved.setdefault('maintenance_id', f"MNT-{uuid.uuid4().hex[:10].upper()}")
        saved.setdefault('created_at', datetime.now(timezone.utc).isoformat())
        return self._save_record('maintenance', 'maintenance_id', saved)

    def update_maintenance(self, maintenance_id: str, payload: Dict[str, Any]):
        record = next((item for item in self.get_maintenance() if item['maintenance_id'] == maintenance_id), None)
        if record is None:
            raise KeyError(f'Maintenance record {maintenance_id} not found')
        record.update(payload)
        return self._save_record('maintenance', 'maintenance_id', record)

    def set_model_metadata(self, payload: Dict[str, Any]):
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                'INSERT INTO app_metadata (key, payload) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET payload = excluded.payload',
                ('model_metadata', json.dumps(payload, default=str)),
            )
        return payload

    def get_model_metadata(self) -> Dict[str, Any]:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute('SELECT payload FROM app_metadata WHERE key = ?', ('model_metadata',)).fetchone()
        return json.loads(row[0]) if row else super().get_model_metadata()


class DataStore:
    def __init__(self):
        self.memory = MemoryRepository()
        self.mongo = MongoRepository()
        self.repository = self.mongo.repository()
        self.storage_backend = 'mongodb_atlas' if isinstance(self.repository, MongoRepository) else 'sqlite_fallback'

    def get_dashboard_summary(self):
        return self.repository.get_dashboard_summary()

    def get_equipment(self):
        return self.repository.get_equipment()

    def get_alerts(self):
        return self.repository.get_alerts()

    def get_alert(self, alert_id):
        return self.repository.get_alert(alert_id)

    def update_alert(self, alert_id, payload):
        return self.repository.update_alert(alert_id, payload)

    def create_alerts(self, alerts):
        return self.repository.create_alerts(alerts)

    def save_predictions(self, rows):
        return self.repository.save_predictions(rows)

    def get_predictions(self, **kwargs):
        return self.repository.get_predictions(**kwargs)

    def get_latest_predictions(self):
        return self.repository.get_latest_predictions()

    def get_maintenance(self):
        return self.repository.get_maintenance()

    def create_maintenance(self, payload):
        return self.repository.create_maintenance(payload)

    def update_maintenance(self, maintenance_id, payload):
        return self.repository.update_maintenance(maintenance_id, payload)

    def list_datasets(self):
        return self.repository.list_datasets()

    def set_model_metadata(self, payload):
        return self.repository.set_model_metadata(payload)

    def get_model_metadata(self):
        return self.repository.get_model_metadata()
