import { useEffect, useState } from 'react';
import { fetchAlerts, updateAlertStatus } from '../services/api';
import { buildAlertQuery } from '../utils/alerts';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [filters, setFilters] = useState({ plant_id: '', equipment_id: '', severity: '', status: '', date_from: '', date_to: '' });
  const [draftFilters, setDraftFilters] = useState(filters);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchAlerts(buildAlertQuery(filters, page))
      .then((payload) => { setAlerts(payload.items || []); setCount(payload.count || 0); setError(''); })
      .catch(() => setError('Could not load alerts from the backend.'));
  }, [filters, page, refreshKey]);

  const onStatusChange = async (alertId, status) => {
    try {
      await updateAlertStatus(alertId, { status });
      setRefreshKey((value) => value + 1);
    } catch {
      setError('Alert status update failed.');
    }
  };

  const saveAlertField = async (alertId, field, value) => {
    try {
      await updateAlertStatus(alertId, { [field]: value });
      setRefreshKey((current) => current + 1);
    } catch {
      setError('Alert details could not be saved.');
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Alerts</p>
          <h2>Maintenance alerts</h2>
        </div>
      </div>

      <div className="filter-row">
        <input aria-label="Filter by plant" placeholder="Plant ID" value={draftFilters.plant_id} onChange={(event) => setDraftFilters({ ...draftFilters, plant_id: event.target.value })} />
        <input aria-label="Filter by equipment" placeholder="Equipment ID" value={draftFilters.equipment_id} onChange={(event) => setDraftFilters({ ...draftFilters, equipment_id: event.target.value })} />
        <select aria-label="Filter by severity" value={draftFilters.severity} onChange={(event) => setDraftFilters({ ...draftFilters, severity: event.target.value })}>
          <option value="">All severities</option><option>Low</option><option>Medium</option><option>High</option><option>Critical</option>
        </select>
        <select aria-label="Filter by status" value={draftFilters.status} onChange={(event) => setDraftFilters({ ...draftFilters, status: event.target.value })}>
          <option value="">All statuses</option><option>Open</option><option>Acknowledged</option><option>In Progress</option><option>Resolved</option>
        </select>
        <input type="date" aria-label="Detected from" value={draftFilters.date_from} onChange={(event) => setDraftFilters({ ...draftFilters, date_from: event.target.value })} />
        <input type="date" aria-label="Detected through" value={draftFilters.date_to} onChange={(event) => setDraftFilters({ ...draftFilters, date_to: event.target.value })} />
        <button className="secondary-button" onClick={() => { setFilters(draftFilters); setPage(0); }}>Apply filters</button>
      </div>
      {error && <p className="status-note error">{error}</p>}
      <p className="status-note">{count} matching alert events</p>

      <div className="panel">
        <div className="table-scroll">
        <table className="data-table alerts-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Plant</th>
              <th>Equipment</th>
              <th>Severity</th>
              <th>Detected at</th>
              <th>Status</th>
              <th>Score</th>
              <th>Measurements</th>
              <th>Explanation</th>
              <th>Technician</th>
              <th>Resolution notes</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr key={alert.alert_id}>
                <td>{alert.alert_id}</td>
                <td>{alert.plant_id}</td>
                <td>{alert.equipment_id}</td>
                <td>{alert.severity}</td>
                <td>{alert.timestamp || 'Unavailable'}</td>
                <td>{alert.status}</td>
                <td>{alert.anomaly_score ?? 'Unavailable'}</td>
                <td>{Object.entries(alert.observed_measurements || {}).map(([key, value]) => `${key}: ${value ?? 'N/A'}`).join(', ') || 'Unavailable'} (units not declared)</td>
                <td>{alert.explanation}</td>
                <td><input aria-label={`Technician for ${alert.alert_id}`} defaultValue={alert.technician || ''} onBlur={(event) => saveAlertField(alert.alert_id, 'technician', event.target.value)} /></td>
                <td><input aria-label={`Resolution notes for ${alert.alert_id}`} defaultValue={alert.resolution_notes || ''} onBlur={(event) => saveAlertField(alert.alert_id, 'resolution_notes', event.target.value)} /></td>
                <td>
                  <select value={alert.status} onChange={(e) => onStatusChange(alert.alert_id, e.target.value)}>
                    <option value="Open">Open</option>
                    <option value="Acknowledged">Acknowledged</option>
                    <option value="In Progress">In Progress</option>
                    <option value="Resolved">Resolved</option>
                  </select>
                </td>
              </tr>
            ))}
            {alerts.length === 0 && <tr><td colSpan="12">No alerts match these filters.</td></tr>}
          </tbody>
        </table>
        </div>
      </div>
      <div className="action-row">
        <button className="secondary-button" disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>Previous</button>
        <span>Page {page + 1} of {Math.max(1, Math.ceil(count / 100))}</span>
        <button className="secondary-button" disabled={(page + 1) * 100 >= count} onClick={() => setPage((value) => value + 1)}>Next</button>
      </div>
    </div>
  );
}
