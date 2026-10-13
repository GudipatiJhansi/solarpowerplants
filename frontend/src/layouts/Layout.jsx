import { NavLink, Outlet } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { BarChart3, BellRing, Database, LayoutDashboard, SunMedium, Wrench, Activity, Menu } from 'lucide-react';
import { fetchDashboardSummary, fetchHealth } from '../services/api';

const navItems = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'Equipment', to: '/equipment', icon: Activity },
  { label: 'Data', to: '/data', icon: Database },
  { label: 'Alerts', to: '/alerts', icon: BellRing },
  { label: 'Maintenance', to: '/maintenance', icon: Wrench },
  { label: 'Model', to: '/model-analytics', icon: BarChart3 },
];

export default function Layout() {
  const [status, setStatus] = useState({ dataSource: 'Checking dataset…', freshness: null, storage: 'Checking storage…' });

  useEffect(() => {
    Promise.all([fetchDashboardSummary(), fetchHealth()]).then(([summary, health]) => {
      setStatus({
        dataSource: summary.data_source || health.data_source || 'No dataset available',
        freshness: summary.data_freshness,
        storage: health.storage_backend === 'mongodb_atlas' ? 'MongoDB Atlas' : 'SQLite local persistence',
      });
    }).catch(() => setStatus({ dataSource: 'Backend unavailable', freshness: null, storage: 'Unavailable' }));
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><SunMedium size={18} /></div>
          <div>
            <strong>Solar AI</strong>
            <small>Predictive Ops</small>
          </div>
        </div>

        <nav className="nav">
          {navItems.map(({ label, to, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="status-pill">{status.storage}</div>
          <small>{status.dataSource}</small>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-title">
            <button className="icon-button" aria-label="Toggle menu"><Menu size={16} /></button>
            <div>
              <p>Monitoring</p>
              <h1>AI-Based Predictive Maintenance</h1>
            </div>
          </div>

          <div className="topbar-meta">
            <div className="pill success">{status.dataSource}</div>
            <div className="pill neutral">Latest record: {status.freshness ? new Date(status.freshness).toLocaleString() : 'Unavailable'}</div>
            <div className="user-badge">AS</div>
          </div>
        </header>

        <Outlet />
      </main>
    </div>
  );
}
