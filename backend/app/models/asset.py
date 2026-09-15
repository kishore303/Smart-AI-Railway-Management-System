from sqlalchemy import Column, BigInteger, String, Date, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from app.database import Base


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("condition_score BETWEEN 0 AND 100", name="assets_condition_score_check"),
        CheckConstraint("asset_health_score BETWEEN 0 AND 100", name="assets_health_score_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    asset_code = Column(String(30), nullable=False, unique=True)
    name = Column(String(150), nullable=True)
    asset_type = Column(String(50), nullable=False)
    department_id = Column(BigInteger, ForeignKey("departments.id"), nullable=False)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=True)
    track_id = Column(BigInteger, ForeignKey("tracks.id"), nullable=True)
    installation_date = Column(Date, nullable=True)
    condition_score = Column(Numeric(5, 2), nullable=True)
    asset_health_score = Column(Numeric(5, 2), nullable=True)
    last_inspection_date = Column(Date, nullable=True)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    status = Column(String(30), nullable=False, server_default="ACTIVE")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AssetSensorReading(Base):
    __tablename__ = "asset_sensor_readings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    asset_id = Column(BigInteger, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    rail_wear_mm = Column(Numeric(6, 2), nullable=True)
    wheel_wear_percent = Column(Numeric(5, 2), nullable=True)
    vibration_level = Column(Numeric(6, 3), nullable=True)
    ballast_condition = Column(String(30), nullable=True)
    track_curvature_degree = Column(Numeric(6, 3), nullable=True)
    ambient_temperature_c = Column(Numeric(5, 2), nullable=True)
    humidity_percent = Column(Numeric(5, 2), nullable=True)
    rainfall_mm = Column(Numeric(6, 2), nullable=True)
    axle_temperature_c = Column(Numeric(5, 2), nullable=True)
    bearing_temperature_c = Column(Numeric(5, 2), nullable=True)
    traction_motor_temp_c = Column(Numeric(5, 2), nullable=True)
    brake_pressure_psi = Column(Numeric(6, 2), nullable=True)
    brake_pad_wear_percent = Column(Numeric(5, 2), nullable=True)
    signal_system_status = Column(String(30), nullable=True)
    inspection_score = Column(Numeric(5, 2), nullable=True)
    sensor_health_index = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AssetFailureHistory(Base):
    __tablename__ = "asset_failure_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    asset_id = Column(BigInteger, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    failure_type = Column(String(100), nullable=True)
    failure_date = Column(DateTime(timezone=True), nullable=False)
    description = Column(String, nullable=True)
    downtime_mins = Column(BigInteger, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
