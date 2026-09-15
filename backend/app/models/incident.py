from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, ForeignKey, Text
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
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    reported_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reported_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    railway_alert_status = Column(String(30), nullable=True)
    police_alert_status = Column(String(30), nullable=True)
    response_status = Column(String, nullable=False, server_default="OPEN")
    clearance_time = Column(DateTime(timezone=True), nullable=True)


class EmergencyResponse(Base):
    __tablename__ = "emergency_responses"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    incident_id = Column(BigInteger, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    authority_type = Column(String(50), nullable=True)
    authority_name = Column(String(150), nullable=True)
    notification_time = Column(DateTime(timezone=True), nullable=True)
    acknowledgement_time = Column(DateTime(timezone=True), nullable=True)
    arrival_time = Column(DateTime(timezone=True), nullable=True)
    clearance_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, server_default="ALERT_RECEIVED")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
