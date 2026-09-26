from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from app.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    incident_code = Column(String(30), nullable=False, unique=True)
    incident_type = Column(String, nullable=False)
    severity = Column(String, nullable=False, server_default="HIGH")
    description = Column(Text, nullable=True)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=True)
    track_id = Column(BigInteger, ForeignKey("tracks.id"), nullable=True)
    asset_id = Column(BigInteger, ForeignKey("assets.id"), nullable=True)
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    
    # Workflow Status
    status = Column(String(50), nullable=False, server_default="REPORTED")
    response_status = Column(String, nullable=False, server_default="OPEN")
    
    # Reporting
    reported_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reported_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    
    # Alerts
    railway_alert_status = Column(String(30), nullable=True)
    police_alert_status = Column(String(30), nullable=True)
    
    # Acknowledgement & Assessment
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    assessed_at = Column(DateTime(timezone=True), nullable=True)
    assessed_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    assessment_notes = Column(Text, nullable=True)
    
    # Emergency Block Request & Selected Decision
    block_request_id = Column(BigInteger, ForeignKey("block_requests.id"), nullable=True)
    selected_optimized_block_id = Column(BigInteger, ForeignKey("optimized_blocks.id"), nullable=True)
    
    # Clearance & Closure
    clearance_time = Column(DateTime(timezone=True), nullable=True)
    cleared_at = Column(DateTime(timezone=True), nullable=True)
    cleared_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    clearance_notes = Column(Text, nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    
    # Flags
    is_simulated = Column(Boolean, nullable=False, server_default="false")

    # Relationships
    section = relationship("RailwaySection", foreign_keys=[section_id], lazy="joined")
    track = relationship("Track", foreign_keys=[track_id], lazy="joined")
    reporter = relationship("User", foreign_keys=[reported_by], lazy="joined")
    acknowledger_user = relationship("User", foreign_keys=[acknowledged_by], lazy="joined")
    assessor_user = relationship("User", foreign_keys=[assessed_by], lazy="joined")
    block_request = relationship("BlockRequest", foreign_keys=[block_request_id], lazy="joined")
    selected_optimized_block = relationship("OptimizedBlock", foreign_keys=[selected_optimized_block_id], lazy="joined")
    responses = relationship("EmergencyResponse", back_populates="incident", cascade="all, delete-orphan", lazy="selectin")


class EmergencyResponse(Base):
    __tablename__ = "emergency_responses"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    incident_id = Column(BigInteger, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    authority_type = Column(String(50), nullable=True)
    authority_name = Column(String(150), nullable=True)
    team_name = Column(String(150), nullable=True)
    assigned_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    
    notification_time = Column(DateTime(timezone=True), nullable=True)
    acknowledgement_time = Column(DateTime(timezone=True), nullable=True)
    arrival_time = Column(DateTime(timezone=True), nullable=True)
    work_start_time = Column(DateTime(timezone=True), nullable=True)
    completion_time = Column(DateTime(timezone=True), nullable=True)
    clearance_time = Column(DateTime(timezone=True), nullable=True)
    
    status = Column(String, nullable=False, server_default="ALERT_RECEIVED")
    notes = Column(Text, nullable=True)
    assigned_resources = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    incident = relationship("Incident", back_populates="responses")
    assigner = relationship("User", foreign_keys=[assigned_by], lazy="joined")
