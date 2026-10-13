import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import Plot from 'react-plotly.js';
import { fetchAlerts, fetchEquipment, fetchEquipmentHistory, fetchMaintenance } from '../services/api';

export default function EquipmentDetailPage() {
  const { equipmentId } = useParams();
  const [records, setRecords] = useState([]);
  const [equipment, setEquipment] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [maintenance, setMaintenance] = useState([]);

  useEffect(() => {
    Promise.all([fetchEquipmentHistory(equipmentId), fetchEquipment(), fetchAlerts({ equipment_id: equipmentId }), fetchMaintenance()])
      .then(([history, assets, alertData, maintenanceData]) => {
        setRecords(history.records || []);
        setEquipment(assets.find((item) => item.equipment_id === equipmentId) || null);
        setAlerts(alertData.items || []);
        setMaintenance((maintenanceData.items || []).filter((item) => item.equipment_id === equipmentId));
      })
      .catch(() => { setRecords([]); setAlerts([]); setMaintenance([]); });
  }, [equipmentId]);

  const orderedRecords = [...records].sort((left, right) => String(left.timestamp).localeCompare(String(right.timestamp)));
  const timestamps = orderedRecords.map((row) => row.timestamp);
  const power = orderedRecords.map((row) => row.power_kw);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Equipment</p>
          <h2>{equipmentId}</h2>
          {equipment && <p>Plant {equipment.plant_id} · latest historical record {equipment.last_recorded_at || 'unavailable'}</p>}
        </div>
      </div>

      <div className="chart-grid single">
        <div className="panel chart-panel">
          <h3>Historical power profile</h3>
          <Plot
            data={[{ x: timestamps, y: power, type: 'scatter', mode: 'lines', line: { color: '#25b873' } }]}
            layout={{ margin: { l: 40, r: 10, t: 20, b: 60 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#243b53' } }}
            config={{ responsive: true }}
            style={{ width: '100%', height: '300px' }}
          />
        </div>
      </div>

      <div className="panel">
        <h3>Recent measurements</h3>
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Power (source units)</th>
              <th>Temp</th>
              <th>Irradiation (source units)</th>
              <th>Voltage</th>
            </tr>
          </thead>
          <tbody>
            {records.slice(0, 10).map((record, idx) => (
              <tr key={`${record.timestamp}-${idx}`}>
                <td>{record.timestamp}</td>
                <td>{record.power_kw ?? 'Unavailable'}</td>
                <td>{record.temperature_c == null ? 'Unavailable' : `${record.temperature_c}°C`}</td>
                <td>{record.irradiance_w_m2 ?? 'Unavailable'}</td>
                <td>{record.voltage_v == null ? 'Unavailable' : `${record.voltage_v} V`}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      <div className="panel">
        <h3>Alerts</h3>
        {alerts.length ? alerts.map((alert) => <p key={alert.alert_id}>{alert.timestamp} · {alert.severity} · {alert.status}: {alert.explanation}</p>) : <p>No alerts recorded for this equipment.</p>}
      </div>

      <div className="panel">
        <h3>Maintenance history</h3>
        {maintenance.length ? maintenance.map((record) => <p key={record.maintenance_id}>{record.created_at || record.scheduled_for || 'Date unavailable'} · {record.title} · {record.status}{record.resolution_notes ? ` · ${record.resolution_notes}` : ''}</p>) : <p>No maintenance records recorded for this equipment.</p>}
      </div>
    </div>
  );
}
