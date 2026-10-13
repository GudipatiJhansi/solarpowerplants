import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Layout from './layouts/Layout';
import DashboardPage from './pages/DashboardPage';
import EquipmentPage from './pages/EquipmentPage';
import DataManagementPage from './pages/DataManagementPage';
import AlertsPage from './pages/AlertsPage';
import MaintenancePage from './pages/MaintenancePage';
import ModelAnalyticsPage from './pages/ModelAnalyticsPage';
import EquipmentDetailPage from './pages/EquipmentDetailPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="/equipment" element={<EquipmentPage />} />
          <Route path="/equipment/:equipmentId" element={<EquipmentDetailPage />} />
          <Route path="/data" element={<DataManagementPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/maintenance" element={<MaintenancePage />} />
          <Route path="/model-analytics" element={<ModelAnalyticsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
