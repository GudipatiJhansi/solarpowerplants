import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchEquipment } from '../services/api';

export default function EquipmentPage() {
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState('');

  useEffect(() => {
    fetchEquipment().then(setItems).catch(() => setItems([]));
  }, []);

  const filtered = items.filter((entry) => `${entry.equipment_id} ${entry.plant_id}`.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Assets</p>
          <h2>Equipment monitoring</h2>
        </div>
        <input className="search-input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search equipment ID or plant" />
      </div>
      <p className="status-note">The relative condition index is derived from the saved model’s normalized anomaly score. It is not a validated failure probability or certified equipment-health measure.</p>

      <div className="panel">
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Equipment ID</th>
              <th>Plant</th>
              <th>Latest power (source units)</th>
              <th>Latest temp</th>
              <th>Relative condition</th>
              <th>Anomaly status</th>
              <th>Risk</th>
              <th>Last record</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.equipment_id}>
                <td><Link to={`/equipment/${item.equipment_id}`}>{item.equipment_id}</Link></td>
                <td>{item.plant_id}</td>
                <td>{item.latest_power_kw ?? 'Unavailable'}</td>
                <td>{item.latest_temperature_c == null ? 'Unavailable' : `${item.latest_temperature_c}°C`}</td>
                <td>{item.health_score == null ? 'Not scored' : `${item.health_score} / 100`}</td>
                <td>{item.anomaly_status}</td>
                <td>{item.risk_indicator}</td>
                <td>{item.last_recorded_at ? new Date(item.last_recorded_at).toLocaleString() : 'Unavailable'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}
