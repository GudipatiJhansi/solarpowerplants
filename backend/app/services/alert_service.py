from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List


def severity_from_score(score: float) -> str:
    if score >= 0.8:
        return 'Critical'
    if score >= 0.65:
        return 'High'
    if score >= 0.45:
        return 'Medium'
    return 'Low'


def generate_alerts(anomaly_rows: List[Dict[str, Any]], grouping_window_minutes: int = 30) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    anomaly_rows = [item for item in anomaly_rows if item.get('anomaly_label', 1) == -1]
    grouped: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
    for item in anomaly_rows:
        key = (str(item.get('plant_id', 'UNKNOWN')), str(item.get('equipment_id', 'UNKNOWN')))
        grouped.setdefault(key, []).append(item)

    events = []
    for (plant_id, equipment_id), rows in grouped.items():
        ordered = sorted(rows, key=lambda row: str(row.get('timestamp') or ''))
        cluster: List[Dict[str, Any]] = []
        for row in ordered:
            timestamp = row.get('timestamp')
            current = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if isinstance(timestamp, str) else timestamp
            previous = cluster[-1].get('timestamp') if cluster else None
            previous = datetime.fromisoformat(previous.replace('Z', '+00:00')) if isinstance(previous, str) else previous
            if cluster and current and previous and current - previous > timedelta(minutes=grouping_window_minutes):
                events.append((plant_id, equipment_id, cluster))
                cluster = []
            cluster.append(row)
        if cluster:
            events.append((plant_id, equipment_id, cluster))

    for plant_id, equipment_id, rows in events:
        item = max(rows, key=lambda row: float(row.get('anomaly_score', 0.0)))
        score = float(item.get('anomaly_score', 0.0))
        deviations = item.get('feature_deviations', [])
        observed = item.get('observed_measurements', {})
        feature_evidence = [
            {**deviation, 'observed_value': observed.get(deviation['feature'])}
            for deviation in deviations
        ]
        timestamp = item.get('timestamp') or 'UNKNOWN'
        event_start = rows[0].get('timestamp') or timestamp
        stable_key = f'{plant_id}|{equipment_id}|{event_start}'
        alert_id = f"ALT-{hashlib.sha256(stable_key.encode('utf-8')).hexdigest()[:12].upper()}"
        alerts.append({
            'alert_id': alert_id,
            'plant_id': plant_id,
            'equipment_id': equipment_id,
            'timestamp': timestamp,
            'event_start': event_start,
            'event_end': rows[-1].get('timestamp') or timestamp,
            'observations_in_event': len(rows),
            'severity': item.get('severity') or severity_from_score(score),
            'status': 'Open',
            'anomaly_score': round(score, 4),
            'observed_measurements': observed,
            'feature_deviations': feature_evidence,
            'explanation': (
                'Isolation Forest flagged an unusual multivariate profile. Signals listed here exceeded 2.5 training standard deviations: '
                + ', '.join(f"{entry['feature']} (z={entry['z_score']}, observed={entry['observed_value']})" for entry in feature_evidence)
                + '. This is an anomaly indicator, not a confirmed fault.'
                if feature_evidence else
                'Isolation Forest flagged an unusual multivariate profile, but no single signal exceeded the 2.5 standard-deviation explanation threshold. This is an anomaly indicator, not a confirmed fault.'
            ),
            'recommended_action': 'Compare the listed signals with the inverter’s recent operating baseline and review the synchronized weather and generation readings before scheduling inspection.',
            'technician': 'Unassigned',
            'resolution_notes': '',
        })
    return alerts
