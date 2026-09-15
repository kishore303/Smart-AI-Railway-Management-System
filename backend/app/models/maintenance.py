from sqlalchemy import Column, BigInteger, String, Integer, Numeric, DateTime, ForeignKey, CheckConstraint, Text, JSON, Boolean
from sqlalchemy.dialects.postgresql import JSONB, ENUM as PGEnum
from sqlalchemy.sql import func
from app.database import Base


class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"
    __table_args__ = (
        CheckConstraint("requested_end > requested_start", name="maintenance_requests_window_check"),
        CheckConstraint(
            "actual_end IS NULL OR actual_start IS NULL OR actual_end > actual_start",
            name="maintenance_requests_actual_check",
        ),
        CheckConstraint("reviewed_by IS NULL OR reviewed_by <> requested_by", name="maintenance_requests_self_approval_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_code = Column(String(30), nullable=False, unique=True)
    asset_id = Column(BigInteger, ForeignKey("assets.id"), nullable=False)
    department_id = Column(BigInteger, ForeignKey("departments.id"), nullable=False)
    requested_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=False)
    track_id = Column(BigInteger, ForeignKey("tracks.id"), nullable=True)
    maintenance_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(PGEnum("LOW","MEDIUM","HIGH","CRITICAL", name="severity_level", create_type=False), nullable=False, server_default="MEDIUM")
    requested_start = Column(DateTime(timezone=True), nullable=False)
    requested_end = Column(DateTime(timezone=True), nullable=False)
    requested_duration_mins = Column(Integer, nullable=True)
    status = Column(PGEnum("DRAFT","SUBMITTED","PENDING","UNDER_REVIEW","VERIFIED","REJECTED","REVISION_REQUIRED","BLOCK_PLANNING","AI_RECOMMENDATION","OFFICIAL_REVIEW","APPROVED","MODIFIED","IN_PROGRESS","COMPLETED", name="maintenance_request_status", create_type=False), nullable=False, server_default="DRAFT")

    reviewed_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    revision_notes = Column(Text, nullable=True)

    actual_start = Column(DateTime(timezone=True), nullable=True)
    actual_end = Column(DateTime(timezone=True), nullable=True)
    actual_duration_mins = Column(Integer, nullable=True)
    actual_workers_used = Column(Integer, nullable=True)
    actual_equipment_count = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class MaintenancePrediction(Base):
    __tablename__ = "maintenance_predictions"
    __table_args__ = (
        CheckConstraint("asset_risk_score BETWEEN 0 AND 1", name="maintenance_predictions_risk_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    maintenance_request_id = Column(BigInteger, ForeignKey("maintenance_requests.id", ondelete="CASCADE"), nullable=False)
    asset_risk_score = Column(Numeric(4, 3), nullable=True)
    risk_level = Column(PGEnum("LOW","MEDIUM","HIGH","CRITICAL", name="severity_level", create_type=False), nullable=True)
    predicted_duration_mins = Column(Integer, nullable=True)
    train_impact_score = Column(Numeric(6, 3), nullable=True)
    predicted_delay_mins = Column(Integer, nullable=True)
    affected_train_count = Column(Integer, nullable=True)
    model_version = Column(String(50), nullable=True)
    input_features = Column(JSONB, nullable=True)
    predicted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MlModelRegistry(Base):
    __tablename__ = "ml_model_registry"
    __table_args__ = (
        CheckConstraint("model_type IN ('ASSET_RISK','MAINTENANCE_DURATION','TRAIN_IMPACT')", name="ml_model_registry_type_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_type = Column(String(30), nullable=False)
    version = Column(String(50), nullable=False)
    artifact_filename = Column(String(255), nullable=True)
    is_demo = Column(Boolean, nullable=False, server_default="true")
    is_active = Column(Boolean, nullable=False, server_default="false")
    trained_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
