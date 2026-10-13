import { useEffect, useState } from 'react';
import { fetchDatasets, uploadDataset } from '../services/api';

export default function DataManagementPage() {
  const [datasets, setDatasets] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [message, setMessage] = useState('');

  const refresh = () => fetchDatasets().then((payload) => setDatasets(payload.items || [])).catch(() => setDatasets([]));

  useEffect(() => { refresh(); }, []);

  const onUpload = async () => {
    if (!selectedFiles.length) {
      setMessage('Choose a CSV file before uploading.');
      return;
    }
    try {
      const results = [];
      for (const file of selectedFiles) {
        const result = await uploadDataset(file);
        results.push(`${file.name}: ${result.message || 'uploaded'}`);
      }
      setMessage(results.join(' '));
      setSelectedFiles([]);
      refresh();
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Upload failed.');
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Data</p>
          <h2>Dataset management</h2>
        </div>
      </div>

      <div className="panel upload-panel">
        <h3>CSV upload</h3>
        <div className="upload-row">
          <input type="file" accept=".csv" multiple onChange={(e) => setSelectedFiles(Array.from(e.target.files || []))} />
          <button className="primary-button" onClick={onUpload}>Upload dataset</button>
        </div>
        {message && <p className="status-note">{message}</p>}
      </div>

      <div className="panel">
        <h3>Available datasets</h3>
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Source</th>
              <th>Date range</th>
              <th>Rows</th>
              <th>Columns</th>
              <th>Size</th>
              <th>Data quality</th>
              <th>Preprocessing</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((dataset) => (
              <tr key={dataset.dataset_id || dataset.filename}>
                <td>{dataset.filename}</td>
                <td>{dataset.source}</td>
                <td>{dataset.date_start || 'N/A'} — {dataset.date_end || 'N/A'}</td>
                <td>{dataset.row_count}</td>
                <td>{dataset.column_count}</td>
                <td>{dataset.file_size_bytes ? `${(dataset.file_size_bytes / 1024 / 1024).toFixed(2)} MB` : 'N/A'}</td>
                <td>{dataset.quality || 'unknown'}</td>
                <td>{dataset.preprocessing_status || 'unknown'}</td>
                <td>{dataset.status}</td>
              </tr>
            ))}
            {datasets.length === 0 && <tr><td colSpan="9">No CSV datasets are available.</td></tr>}
          </tbody>
        </table>
        </div>
      </div>
      {datasets.map((dataset) => (
        <details className="panel" key={`${dataset.dataset_id}-inspection`}>
          <summary>{dataset.filename} inspection</summary>
          <p><strong>Date range:</strong> {dataset.date_start || 'Unavailable'} to {dataset.date_end || 'Unavailable'}</p>
          <p><strong>Timestamp timezone:</strong> {dataset.timestamp_timezone || 'Not declared by source'}</p>
          <p><strong>Columns:</strong> {(dataset.column_names || []).join(', ') || 'Not inspected'}</p>
          {dataset.data_types && <p><strong>Data types:</strong> {Object.entries(dataset.data_types).map(([column, type]) => `${column}: ${type}`).join(', ')}</p>}
          {dataset.measurement_units && <p><strong>Units:</strong> {Object.entries(dataset.measurement_units).map(([column, unit]) => `${column}: ${unit}`).join(', ')}</p>}
          {dataset.measurement_columns && <p><strong>Measurements by category:</strong> {Object.entries(dataset.measurement_columns).map(([category, columns]) => `${category}: ${columns.join(', ') || 'unavailable'}`).join(' | ')}</p>}
          <p><strong>Detected features:</strong> {(dataset.supported_features || []).join(', ') || 'None detected'}</p>
          <p><strong>Verified failure labels:</strong> {dataset.verified_failure_labels_exist ? 'Present' : 'Not present'}</p>
          <p><strong>Anomaly detection suitable:</strong> {dataset.suitable_for_anomaly_detection ? 'Yes' : 'No'}</p>
          <p><strong>Supervised classification suitable:</strong> {dataset.suitable_for_supervised_classification ? 'Yes' : 'No'}</p>
          {dataset.duplicate_rows != null && <p><strong>Duplicate rows:</strong> {dataset.duplicate_rows}</p>}
          {dataset.invalid_measurements && <p><strong>Physically invalid values:</strong> {Object.entries(dataset.invalid_measurements).map(([column, count]) => `${column}: ${count}`).join(', ')}</p>}
          {dataset.statistical_outliers && <p><strong>Potential IQR outliers (retained):</strong> {Object.entries(dataset.statistical_outliers).map(([column, count]) => `${column}: ${count}`).join(', ')}</p>}
          {dataset.missing_values && <p><strong>Missing values:</strong> {Object.entries(dataset.missing_values).map(([column, count]) => `${column}: ${count}`).join(', ')}</p>}
          {(dataset.warnings || []).map((warning) => <p className="status-note" key={warning}>{warning}</p>)}
          {(dataset.errors || []).map((error) => <p className="status-note error" key={error}>{error}</p>)}
        </details>
      ))}
    </div>
  );
}
