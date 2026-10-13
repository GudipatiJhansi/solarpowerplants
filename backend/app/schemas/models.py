from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DatasetInspectRequest(BaseModel):
    file_path: str


class DatasetUploadRequest(BaseModel):
    file_name: str
    file_size: int
    content_type: Optional[str] = None


class DatasetInfo(BaseModel):
    dataset_id: str
    filename: str
    source: str
    data_source: str
    file_size_bytes: int
    row_count: int
    column_count: int
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    status: str
    quality: str
    preprocessing_status: str = 'pending'
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class AlertUpdateRequest(BaseModel):
    status: Optional[Literal['Open', 'Acknowledged', 'In Progress', 'Resolved']] = None
    acknowledged_by: Optional[str] = None
    technician: Optional[str] = None
    resolution_notes: Optional[str] = None


class MaintenanceRecordRequest(BaseModel):
    equipment_id: str
    plant_id: str
    title: str
    description: str
    maintenance_type: str = 'inspection'
    status: Literal['scheduled', 'in_progress', 'completed', 'cancelled'] = 'scheduled'
    scheduled_for: Optional[str] = None
    technician: Optional[str] = None
    resolution_notes: Optional[str] = None


class MaintenanceRecordUpdateRequest(BaseModel):
    status: Optional[Literal['scheduled', 'in_progress', 'completed', 'cancelled']] = None
    scheduled_for: Optional[str] = None
    technician: Optional[str] = None
    resolution_notes: Optional[str] = None
    description: Optional[str] = None
    title: Optional[str] = None
    maintenance_type: Optional[str] = None


class ModelTrainingRequest(BaseModel):
    file_path: Optional[str] = None
    contamination: float = Field(default=0.08, ge=0.001, le=0.2)


class ModelPredictionRequest(BaseModel):
    file_path: Optional[str] = None


class DashboardSummary(BaseModel):
    total_plants: int
    total_equipment: int
    latest_power_kw: float
    avg_health_score: float
    active_alerts: int
    critical_alerts: int
    energy_generation_kwh: float
    data_source: str
    data_freshness: str
    monitored_period: str


class HealthResponse(BaseModel):
    status: str
    message: str
    data_source: str
    demo_mode: bool
    storage_backend: str
