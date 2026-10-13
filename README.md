# AI-Based Predictive Maintenance System for Smart Solar Power Plants

## Project overview
This project is a full-stack solar monitoring and predictive maintenance application designed for a B.Tech final-year demonstration. It includes a FastAPI backend, a React + Vite dashboard, Polars-based dataset inspection and preprocessing, and an unsupervised anomaly detection workflow for equipment monitoring.

## Problem statement
Solar power plants generate large quantities of time-series operational data. Without automated monitoring, faults such as inverter overheating, voltage instability, or abnormal generation profiles may go unnoticed until they result in downtime. This project provides a practical dashboard for monitoring plant performance, inspecting datasets, detecting anomalies, and managing maintenance actions.

## Objectives
- Inspect and validate CSV-based solar datasets.
- Clean and preprocess time-series measurements.
- Train an anomaly detector on actual available signals.
- Present health indicators and alert information.
- Manage maintenance records and equipment monitoring.
- Keep the application demonstrable without real hardware or a live MongoDB instance.

## System architecture
The system is organized into four main modules:
1. Data ingestion and validation module.
2. ML anomaly detection and health scoring module.
3. FastAPI service layer and MongoDB/SQLite persistence abstraction.
4. React interface for dashboard, equipment, alerts, and maintenance pages.

## Technology stack
- Frontend: React, Vite, JavaScript, React Router, Plotly.js, Lucide React
- Backend: Python, FastAPI, Uvicorn, Pydantic, Polars
- ML: PyOD, scikit-learn, NumPy, Pandas, Joblib
- Database: MongoDB Atlas with PyMongo, plus persistent local SQLite fallback
- Testing: Pytest

## Dataset source and attribution
The locally supplied extracted archive was found under `C:\Users\Admin\Downloads\solardatasets`. The original Kaggle listing URL, owner, and license metadata were not present in the archive and have not been guessed. The files currently integrated are:
- Plant_1_Generation_Data.csv
- Plant_1_Weather_Sensor_Data.csv
- Plant_2_Generation_Data.csv
- Plant_2_Weather_Sensor_Data.csv

These CSVs were verified to contain the following data characteristics:
- Date range: 2020-05-15 to 2020-06-17
- Rows: 68,778 and 67,698 for the generation files; weather files contain 3,182 and 3,259 rows
- Core fields: DATE_TIME, PLANT_ID, SOURCE_KEY, DC_POWER, AC_POWER, DAILY_YIELD, TOTAL_YIELD, AMBIENT_TEMPERATURE, MODULE_TEMPERATURE, IRRADIATION
- The source files do not declare a timezone or measurement units in their headers. Timestamps are retained as timezone-naive local records; the app does not append a UTC marker.
- Generation and weather data are left-joined on plant ID and timestamp only after checking weather-key uniqueness. Four generation observations have no matching weather sample and remain missing rather than receiving fabricated values.

The files contain historical data from 2020, so they do not meet the requested 2024–2025 preference. No 2024–2025 source data has been fabricated or substituted. Confirm the exact Kaggle dataset URL, author, and license from the original listing before formal citation.

The project still keeps a reproducible demo dataset under backend/data/sample/demo_solar_data.csv for UI testing and offline demonstration; it is explicitly labeled simulated and is never used as a substitute for the verified real power-plant CSVs.

## Dataset placement instructions
Place original Kaggle CSV files in `backend/data/raw/`. Related generation and weather files may be selected and uploaded together in the Data page. Derived files belong in `backend/data/processed/`; original files are never preprocessed in place.

The raw directory is reserved for original CSVs, while processed contains derived outputs. The generated demo file remains in backend/data/sample for local demonstration purposes.

## Folder structure
- backend/app/api: FastAPI route handlers
- backend/app/core: configuration and logging
- backend/app/database: MongoDB and SQLite persistence abstraction
- backend/app/services: ingestion, preprocessing, alerting, and ML services
- backend/app/ml: ML helper functions
- backend/data/raw: original CSV files
- backend/data/processed: derived datasets and model outputs
- backend/data/sample: demo dataset and test data
- backend/tests: automated tests
- frontend/src: React pages, components, styles, services

## Windows installation instructions
### 1. Clone or open the project
Open PowerShell in the workspace root.

### 2. Create and activate a virtual environment
```powershell
cd C:\Users\Admin\OneDrive\Desktop\predictivemaintainancesystemsolar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies
```powershell
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Install frontend dependencies
```powershell
cd ..\frontend
npm install
```

## Environment variables
From PowerShell, create `backend/.env` from its example, then set `MONGODB_URI` in that file to your Atlas connection string. Never commit `.env` or expose the URI in frontend code. With an empty URI or an unreachable cluster at startup, the API stores alerts, maintenance records, and model metadata in `backend/data/app_state.sqlite3`.

```powershell
Set-Location C:\Users\Admin\OneDrive\Desktop\predictivemaintainancesystemsolar\backend
Copy-Item .env.example .env
notepad .env
```

Example settings:
```powershell
MONGODB_URI=
MONGODB_DATABASE=solar_predictive_maintenance
FRONTEND_ORIGIN=http://localhost:5173
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
DATASET_DIR=./data
DEMO_MODE=true
```

## MongoDB Atlas setup
1. Create a MongoDB Atlas cluster.
2. Get the connection string.
3. Set MONGODB_URI in the backend .env file.
4. Ensure the application can reach the cluster from the environment.
5. Restart the backend. On successful connection, alerts, maintenance records, and model metadata use Atlas. Uploaded CSV files remain in the local data directory. If Atlas is unavailable, alert and maintenance records remain persistent in the local SQLite fallback.

## Data inspection and preprocessing
```powershell
cd C:\Users\Admin\OneDrive\Desktop\predictivemaintainancesystemsolar\backend
python inspect_dataset.py
python -m pytest tests/test_app.py -q
```

## Model training and inference
```powershell
cd C:\Users\Admin\OneDrive\Desktop\predictivemaintainancesystemsolar\backend
python train_model.py
```

## Frontend and backend startup
### Backend
```powershell
cd C:\Users\Admin\OneDrive\Desktop\predictivemaintainancesystemsolar\backend
. ..\.venv\Scripts\Activate.ps1
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend
```powershell
cd C:\Users\Admin\OneDrive\Desktop\predictivemaintainancesystemsolar\frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## API documentation
The FastAPI application exposes OpenAPI docs at:
- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/redoc

## Test commands
```powershell
cd C:\Users\Admin\OneDrive\Desktop\predictivemaintainancesystemsolar\backend
python -m pytest -q
```

## Data mode and persistence
The current primary data source is the locally supplied historical solar CSV set. API and UI identify it as historical data and display its actual timestamps. The dashboard derives plant, equipment, power, temperature, irradiance, and date values from the CSV files; a validated health score is unavailable because this dataset has no verified fault labels or health ground truth. SQLite persists application records locally when Atlas is not configured. Atlas connectivity must be tested in the user's environment after setting credentials.

The anomaly model uses PyOD Isolation Forest with an 8% configured contamination, a fixed random seed, and the available numeric canonical features. Prediction scores are normalized against the training score range, and severity uses training-set 75th/90th percentile thresholds. Alerts group adjacent anomalous records for the same plant/equipment within 30 minutes. These are anomaly indicators, not validated failure predictions. No supervised model or health score is emitted because the files contain no verified fault labels or health ground truth.

## Limitations and future improvements
- The available solar CSVs cover 2020-05-15 through 2020-06-17; they are historical data, not live telemetry.
- The archive did not include Kaggle attribution or license metadata; confirm those from the original listing if formal citation is required.
- The anomaly detector is unsupervised and should be interpreted as a maintenance-risk indicator rather than a validated fault-probability model.
- MongoDB Atlas is optional for local use; SQLite provides durable alert, maintenance, and model-metadata storage until Atlas is configured.
- A live stream integration or real hardware connection would be required for true real-time monitoring.

## Actual implementation status
Implemented and locally verified:
- FastAPI backend health endpoint
- CSV inspection and preprocessing workflows
- ML model training and artifact persistence
- React dashboard with multiple pages
- Alerts and maintenance management
- Generated anomaly alerts and maintenance records persist across backend restarts
- Generation/weather files are joined on unique plant/timestamp keys; four unmatched weather samples remain missing rather than being fabricated.
- Test coverage for data inspection, preprocessing, joins, anomaly training/inference, persistence, upload validation, and event grouping

Not verified or not available in the current environment:
- MongoDB Atlas writes, because no connection URI is configured.
- Recent 2024–2025 Kaggle files and source attribution.
- Live telemetry, authentication, validated health scoring, and supervised fault evaluation.
