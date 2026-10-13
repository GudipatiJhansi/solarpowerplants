import { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import StatCard from '../components/StatCard';
import { fetchDashboardSummary, fetchDashboardTrends, fetchEquipment } from '../services/api';

export default function DashboardPage() {
  const [summary, setSummary] = useState({
    total_plants: 0,
    total_equipment: 0,
    latest_power_kw: null,
    avg_health_score: null,
    active_alerts: 0,
    critical_alerts: 0,
    energy_generation_kwh: 0,
    data_source: 'loading',
  });
  const [trends, setTrends] = useState({ timestamps: [], power: [], temperature: [], irradiance: [], prediction_timestamps: [], anomaly_scores: [], condition_scores: [] });
  const [equipment, setEquipment] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([fetchDashboardSummary(), fetchDashboardTrends(), fetchEquipment()])
      .then(([summaryData, trendData, equipmentData]) => {
        setSummary(summaryData);
        setTrends(trendData);
        setEquipment(equipmentData);
      })
      .catch(() => setError('Could not load dashboard data. Check the backend connection and retry.'))
      .finally(() => setLoading(false));
  }, []);

  const equipmentWithPower = equipment.filter((item) => item.latest_power_kw != null).sort((left, right) => right.latest_power_kw - left.latest_power_kw).slice(0, 15);
  const equipmentWithCondition = equipment.filter((item) => item.health_score != null).sort((left, right) => right.health_score - left.health_score).slice(0, 15);
  const severity = summary.alert_severity_distribution || {};

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Operations</p>
          <h2>Plant overview</h2>
        </div>
        <div className="pill neutral">{summary.data_source || 'No dataset linked'}</div>
      </div>

      {loading ? <div className="loading-box">Loading dashboard…</div> : (
        <>
          <div className="stats-grid">
            <StatCard label="Monitored plants" value={summary.total_plants} delta="Distinct plant IDs in source data" />
            <StatCard label="Monitored equipment" value={summary.total_equipment} delta="Distinct source keys in generation data" />
            <StatCard
              label="Latest recorded power (source units)"
              value={summary.latest_power_kw == null ? 'Unavailable' : summary.latest_power_kw.toFixed(1)}
              delta={summary.latest_power_kw === 0 && summary.latest_irradiance_w_m2 === 0
                ? 'Nighttime reading · latest irradiance is zero'
                : 'Historical reading · source units not declared'}
              tone="success"
            />
            <StatCard label="Relative condition index" value={summary.avg_health_score == null ? 'Not scored' : `${summary.avg_health_score.toFixed(1)} / 100`} delta="Model-relative, not a validated health measure" tone="default" />
            <StatCard label="Active alerts" value={summary.active_alerts} delta="Open events" tone="warning" />
            <StatCard label="Critical alerts" value={summary.critical_alerts} delta="Immediate action" tone="danger" />
            <StatCard
              label="Energy generation (source units)"
              value={summary.energy_generation_source_units == null ? 'Unavailable' : summary.energy_generation_source_units.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              delta={`Sum of daily inverter yields · ${summary.energy_generation_unit || 'unit unavailable'}`}
            />
          </div>

          <p className="status-note">Historical data: {summary.monitored_period || 'date range unavailable'} · latest record {summary.data_freshness ? new Date(summary.data_freshness).toLocaleString() : 'unavailable'}.</p>
          {error && <p className="status-note error">{error}</p>}

          <div className="chart-grid">
            <div className="panel chart-panel">
              <h3>Power output versus time</h3>
              <Plot
                data={[{ x: trends.timestamps, y: trends.power, type: 'scatter', mode: 'lines', line: { color: '#25b873', width: 3 } }]}
                layout={{ margin: { l: 50, r: 10, t: 20, b: 35 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' }, yaxis: { title: 'Power (source units)' } }}
                config={{ responsive: true }}
                style={{ width: '100%', height: '280px' }}
              />
            </div>

            <div className="panel chart-panel">
              <h3>Temperature trend</h3>
              {trends.temperature.length === 0 && <p className="empty-state">Temperature data is not available in the selected generation file.</p>}
              <Plot
                data={trends.temperature.length ? [{ x: trends.timestamps, y: trends.temperature, type: 'scatter', mode: 'lines', line: { color: '#f59e0b', width: 3 } }] : []}
                layout={{ margin: { l: 40, r: 10, t: 20, b: 35 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' } }}
                config={{ responsive: true }}
                style={{ width: '100%', height: '280px' }}
              />
            </div>

            <div className="panel chart-panel">
              <h3>Irradiation vs power</h3>
              {trends.irradiance.length === 0 && <p className="empty-state">Irradiance data is not available in the selected generation file.</p>}
              <Plot
                data={trends.irradiance.length ? [{ x: trends.irradiance, y: trends.power, mode: 'markers', type: 'scatter', marker: { color: '#0ea5e9', size: 8 } }] : []}
                layout={{ margin: { l: 50, r: 10, t: 20, b: 35 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' }, xaxis: { title: 'Source irradiation value (unit not declared)' }, yaxis: { title: 'Power (source units)' } }}
                config={{ responsive: true }}
                style={{ width: '100%', height: '280px' }}
              />
            </div>

            <div className="panel chart-panel">
              <h3>Model-relative condition trend</h3>
              {trends.condition_scores.length === 0 ? <p className="empty-state">Train the anomaly model and run predictions to calculate this explicitly unvalidated relative index.</p> : (
                <Plot
                  data={[{ x: trends.prediction_timestamps, y: trends.condition_scores, type: 'scatter', mode: 'lines', name: 'Relative condition index', line: { color: '#2563eb', width: 2 } }]}
                  layout={{ margin: { l: 40, r: 10, t: 20, b: 35 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' }, yaxis: { title: 'Index (0–100)', range: [0, 100] } }}
                  config={{ responsive: true }}
                  style={{ width: '100%', height: '280px' }}
                />
              )}
            </div>

            <div className="panel chart-panel">
              <h3>Anomaly score trend</h3>
              {trends.anomaly_scores.length === 0 ? <p className="empty-state">No persisted model predictions yet.</p> : (
                <Plot data={[{ x: trends.prediction_timestamps, y: trends.anomaly_scores, type: 'scatter', mode: 'lines', name: 'Normalized anomaly score', line: { color: '#dc2626', width: 2 } }]} layout={{ margin: { l: 40, r: 10, t: 20, b: 35 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' }, yaxis: { title: 'Training-relative score', range: [0, 1] } }} config={{ responsive: true }} style={{ width: '100%', height: '280px' }} />
              )}
            </div>

            <div className="panel chart-panel">
              <h3>Anomaly score distribution</h3>
              {trends.anomaly_scores.length === 0 ? <p className="empty-state">No persisted model predictions yet.</p> : (
                <Plot data={[{ x: trends.anomaly_scores, type: 'histogram', marker: { color: '#e8793e' }, name: 'Prediction samples' }]} layout={{ margin: { l: 40, r: 10, t: 20, b: 35 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' }, xaxis: { title: 'Training-relative anomaly score' }, yaxis: { title: 'Sample count' } }} config={{ responsive: true }} style={{ width: '100%', height: '280px' }} />
              )}
            </div>

            <div className="panel chart-panel">
              <h3>Alert severity distribution</h3>
              {Object.values(severity).reduce((total, value) => total + value, 0) === 0 ? <p className="empty-state">No generated alert events.</p> : (
                <Plot data={[{ x: Object.keys(severity), y: Object.values(severity), type: 'bar', marker: { color: ['#dc2626', '#e8793e', '#d69e2e', '#64748b'] } }]} layout={{ margin: { l: 40, r: 10, t: 20, b: 35 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' }, yaxis: { title: 'Alert events', rangemode: 'tozero' } }} config={{ responsive: true }} style={{ width: '100%', height: '280px' }} />
              )}
            </div>

            <div className="panel chart-panel">
              <h3>Latest power by equipment</h3>
              {equipmentWithPower.length === 0 ? <p className="empty-state">No power observations are available.</p> : (
                <Plot data={[{ x: equipmentWithPower.map((item) => item.equipment_id), y: equipmentWithPower.map((item) => item.latest_power_kw), type: 'bar', marker: { color: '#25b873' } }]} layout={{ margin: { l: 45, r: 10, t: 20, b: 85 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' }, xaxis: { tickangle: -45 }, yaxis: { title: 'Power (source units)' } }} config={{ responsive: true }} style={{ width: '100%', height: '300px' }} />
              )}
            </div>

            <div className="panel chart-panel">
              <h3>Relative condition by equipment</h3>
              {equipmentWithCondition.length === 0 ? <p className="empty-state">No persisted model scores yet. Run predictions to populate this comparison.</p> : (
                <Plot data={[{ x: equipmentWithCondition.map((item) => item.equipment_id), y: equipmentWithCondition.map((item) => item.health_score), type: 'bar', marker: { color: '#2563eb' } }]} layout={{ margin: { l: 45, r: 10, t: 20, b: 85 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' }, xaxis: { tickangle: -45 }, yaxis: { title: 'Model-relative index', range: [0, 100] } }} config={{ responsive: true }} style={{ width: '100%', height: '300px' }} />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
