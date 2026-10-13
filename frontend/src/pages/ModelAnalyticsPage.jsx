import { useEffect, useState } from 'react';
import { fetchModelStatus, runAnomalyPredictions, trainAnomalyModel } from '../services/api';

export default function ModelAnalyticsPage() {
  const [model, setModel] = useState({
    model_type: 'IsolationForest',
    status: 'not_trained',
    training_dataset: 'not available',
    feature_list: [],
    n_training_records: 0,
    anomaly_count: 0,
    known_limitations: 'Model is not yet trained.',
  });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const refresh = () => fetchModelStatus().then(setModel);

  useEffect(() => {
    refresh().catch(() => setMessage('Could not load model status from the backend.'));
  }, []);

  const run = async (action) => {
    setBusy(true);
    setMessage('');
    try {
      const result = await action();
      if (result.alerts_created_or_existing != null) {
        setMessage(`Processed ${result.prediction_count} daylight observations; excluded ${result.nighttime_records_excluded} zero-irradiation rows; grouped anomalies into ${result.alerts_created_or_existing} events.`);
      } else {
        setMessage(`Model trained on ${result.n_training_records} records using ${result.feature_list.join(', ')}.`);
      }
      await refresh();
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Model operation failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Analytics</p>
          <h2>Model status</h2>
        </div>
        <div className="action-row">
          <button className="secondary-button" disabled={busy} onClick={() => run(trainAnomalyModel)}>Train model</button>
          <button className="primary-button" disabled={busy || model.status === 'not_trained'} onClick={() => run(runAnomalyPredictions)}>Run predictions</button>
        </div>
      </div>
      {message && <p className="status-note">{message}</p>}

      <div className="stats-grid triple">
        <div className="stat-card">
          <div className="stat-label">Model type</div>
          <div className="stat-value">{model.model_type}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Training records</div>
          <div className="stat-value">{model.n_training_records}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Anomaly count</div>
          <div className="stat-value">{model.anomaly_count}</div>
        </div>
      </div>

      <div className="panel">
        <h3>Model details</h3>
        <p><strong>Training dataset:</strong> {model.training_dataset}</p>
        <p><strong>Training timestamp:</strong> {model.training_timestamp || 'Unavailable'}</p>
        <p><strong>Status:</strong> {model.status}</p>
        <p><strong>Features:</strong> {model.feature_list.join(', ') || 'No feature list loaded yet.'}</p>
        <p><strong>Condition index method:</strong> {model.health_score_method || '100 × (1 − normalized anomaly score); model-relative, not validated.'}</p>
        <p><strong>Feature engineering:</strong> {model.feature_engineering || 'Rolling feature description loads after training.'}</p>
        <p><strong>Nighttime handling:</strong> {model.nighttime_filter || 'Zero-irradiation records are excluded from model scoring.'}</p>
        <p><strong>Contamination threshold:</strong> {model.contamination == null ? 'Not available' : `${(model.contamination * 100).toFixed(1)}%`}</p>
        <p><strong>Known limitations:</strong> {model.known_limitations}</p>
        <p>Anomaly scores are not fault probabilities. No verified failure labels are present in the selected CSVs, so supervised fault classification metrics are unavailable.</p>
      </div>
    </div>
  );
}
