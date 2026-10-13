from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title='AI-Based Predictive Maintenance System for Smart Solar Power Plants',
    version='1.0.0',
    description='Industrial solar monitoring, anomaly detection, alerts, and maintenance dashboard.',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, 'http://127.0.0.1:5173', 'http://localhost:5173'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(router, prefix='/api')


@app.get('/')
def root():
    return {'app': 'solar predictive maintenance', 'status': 'running'}
