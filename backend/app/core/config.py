import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')


class Settings:
    mongodb_uri: str = os.getenv('MONGODB_URI', '')
    mongodb_database: str = os.getenv('MONGODB_DATABASE', 'solar_predictive_maintenance')
    frontend_origin: str = os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173')
    backend_host: str = os.getenv('BACKEND_HOST', '127.0.0.1')
    backend_port: int = int(os.getenv('BACKEND_PORT', '8000'))
    data_dir: str = os.getenv('DATASET_DIR', str(Path(__file__).resolve().parents[1] / 'data'))
    demo_mode: bool = os.getenv('DEMO_MODE', 'true').lower() == 'true'
    alert_group_window_minutes: int = int(os.getenv('ALERT_GROUP_WINDOW_MINUTES', '30'))


settings = Settings()
