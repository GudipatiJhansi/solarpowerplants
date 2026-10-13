import { useEffect, useState } from 'react';
import { createMaintenanceRecord, fetchMaintenance, updateMaintenanceRecord } from '../services/api';

export default function MaintenancePage() {
  const [records, setRecords] = useState([]);
  const [form, setForm] = useState({
    equipment_id: '',
    plant_id: '',
    title: '',
    description: '',
    maintenance_type: 'inspection',
    scheduled_for: '',
    technician: '',
    resolution_notes: '',
  });
  const [message, setMessage] = useState('');

  const refresh = () => fetchMaintenance().then((payload) => setRecords(payload.items || [])).catch(() => setRecords([]));

  useEffect(() => { refresh(); }, []);

  const submitForm = async (e) => {
    e.preventDefault();
    try {
      await createMaintenanceRecord({ ...form, scheduled_for: form.scheduled_for || null, technician: form.technician || null });
      setMessage('Maintenance record created.');
      setForm({ equipment_id: '', plant_id: '', title: '', description: '', maintenance_type: 'inspection', scheduled_for: '', technician: '', resolution_notes: '' });
      refresh();
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Could not create maintenance record.');
    }
  };

  const changeStatus = async (record, status) => {
    try {
      await updateMaintenanceRecord(record.maintenance_id, { status });
      refresh();
    } catch {
      setMessage('Could not update maintenance status.');
    }
  };

  const saveResolutionNotes = async (record, resolution_notes) => {
    try {
      await updateMaintenanceRecord(record.maintenance_id, { resolution_notes });
      refresh();
    } catch {
      setMessage('Could not save resolution notes.');
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Maintenance</p>
          <h2>Work orders</h2>
        </div>
      </div>

      <div className="panel">
        <form onSubmit={submitForm} className="maintenance-form">
          <input required value={form.equipment_id} onChange={(e) => setForm({ ...form, equipment_id: e.target.value })} placeholder="Equipment ID" />
          <input required value={form.plant_id} onChange={(e) => setForm({ ...form, plant_id: e.target.value })} placeholder="Plant ID" />
          <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Title" />
          <input value={form.maintenance_type} onChange={(e) => setForm({ ...form, maintenance_type: e.target.value })} placeholder="Type" />
          <input value={form.technician} onChange={(e) => setForm({ ...form, technician: e.target.value })} placeholder="Technician" />
          <input type="datetime-local" value={form.scheduled_for} onChange={(e) => setForm({ ...form, scheduled_for: e.target.value })} aria-label="Scheduled for" />
          <textarea value={form.resolution_notes} onChange={(e) => setForm({ ...form, resolution_notes: e.target.value })} placeholder="Resolution notes (optional)" rows={2} />
          <textarea required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description" rows={4} />
          <button type="submit" className="primary-button">Create record</button>
        </form>
        {message && <p className="status-note">{message}</p>}
      </div>

      <div className="panel">
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Equipment</th>
              <th>Title</th>
              <th>Status</th>
              <th>Scheduled</th>
              <th>Created</th>
              <th>Technician</th>
              <th>Resolution notes</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <tr key={record.maintenance_id}>
                <td>{record.maintenance_id}</td>
                <td>{record.equipment_id}</td>
                <td>{record.title}</td>
                <td><select value={record.status} onChange={(event) => changeStatus(record, event.target.value)}><option value="scheduled">Scheduled</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></td>
                <td>{record.scheduled_for || 'Not scheduled'}</td>
                <td>{record.created_at || 'Unavailable'}</td>
                <td>{record.technician}</td>
                <td><input aria-label={`Resolution notes for ${record.maintenance_id}`} defaultValue={record.resolution_notes || ''} onBlur={(event) => saveResolutionNotes(record, event.target.value)} /></td>
              </tr>
            ))}
            {records.length === 0 && <tr><td colSpan="8">No maintenance records recorded.</td></tr>}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}
