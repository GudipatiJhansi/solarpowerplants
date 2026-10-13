import axios from 'axios';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  timeout: 120000,
});

export const fetchDashboardSummary = async () => (await api.get('/dashboard/summary')).data;
export const fetchDashboardTrends = async () => (await api.get('/dashboard/trends')).data;
export const fetchHealth = async () => (await api.get('/health')).data;
export const fetchPlants = async () => (await api.get('/plants')).data;
export const fetchEquipment = async () => (await api.get('/equipment')).data;
export const fetchEquipmentHistory = async (equipmentId) => (await api.get(`/equipment/${equipmentId}/history`)).data;
export const fetchDatasets = async () => (await api.get('/data/datasets')).data;
export const fetchAlerts = async (params = {}) => (await api.get('/alerts', { params })).data;
export const fetchMaintenance = async () => (await api.get('/maintenance')).data;
export const fetchModelStatus = async () => (await api.get('/ml/status')).data;
export const trainAnomalyModel = async () => (await api.post('/ml/train', {})).data;
export const runAnomalyPredictions = async () => (await api.post('/ml/predict', {})).data;

export const updateAlertStatus = async (alertId, payload) => (await api.patch(`/alerts/${alertId}`, payload)).data;
export const createMaintenanceRecord = async (payload) => (await api.post('/maintenance', payload)).data;
export const updateMaintenanceRecord = async (maintenanceId, payload) => (await api.patch(`/maintenance/${maintenanceId}`, payload)).data;
export const uploadDataset = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return (await api.post('/data/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
};

export default api;
