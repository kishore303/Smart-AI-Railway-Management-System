from app.database import Base

# Import all models so Alembic / Base.metadata sees them
from app.models.department import Department, DepartmentRole  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.station import Station  # noqa: F401
from app.models.railway import RailwaySection, Track  # noqa: F401
from app.models.asset import Asset, AssetSensorReading, AssetFailureHistory  # noqa: F401
from app.models.weather import WeatherReading  # noqa: F401
from app.models.resource import Resource  # noqa: F401
from app.models.train import Train, TrainSchedule  # noqa: F401
from app.models.maintenance import MaintenanceRequest, MaintenancePrediction, MlModelRegistry  # noqa: F401
from app.models.safety import SafetyValidation  # noqa: F401
from app.models.block import (  # noqa: F401
    BlockRequest,
    BlockIntegrationRequest,
    OptimizedBlock,
    BlockCandidate,
    OptimizedBlockSource,
    BlockAffectedTrain,
    BlockResourceAllocation,
)
from app.models.notification import Notification  # noqa: F401
from app.models.incident import Incident, EmergencyResponse  # noqa: F401
from app.models.simulation import Simulation  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401

__all__ = [
    "Base",
    "Department",
    "DepartmentRole",
    "User",
    "Station",
    "RailwaySection",
    "Track",
    "Asset",
    "AssetSensorReading",
    "AssetFailureHistory",
    "WeatherReading",
    "Resource",
    "Train",
    "TrainSchedule",
    "MaintenanceRequest",
    "MaintenancePrediction",
    "MlModelRegistry",
    "BlockRequest",
    "BlockIntegrationRequest",
    "OptimizedBlock",
    "BlockCandidate",
    "OptimizedBlockSource",
    "BlockAffectedTrain",
    "BlockResourceAllocation",
    "Notification",
    "Incident",
    "EmergencyResponse",
    "Simulation",
    "AuditLog",
]
