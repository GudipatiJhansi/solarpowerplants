export default function StatCard({ label, value, delta, tone = 'default' }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {delta && <div className={`stat-delta ${tone}`}>{delta}</div>}
    </div>
  );
}
