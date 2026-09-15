from sqlalchemy import Column, BigInteger, String, Integer, Numeric, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from app.database import Base


class RailwaySection(Base):
    __tablename__ = "railway_sections"
    __table_args__ = (
        CheckConstraint("start_station_id <> end_station_id", name="railway_sections_station_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    section_code = Column(String(20), nullable=False, unique=True)
    name = Column(String(150), nullable=True)
    start_station_id = Column(BigInteger, ForeignKey("stations.id"), nullable=False)
    end_station_id = Column(BigInteger, ForeignKey("stations.id"), nullable=False)
    distance_km = Column(Numeric(7, 2), nullable=True)
    max_speed_kmph = Column(Integer, nullable=True)
    number_of_tracks = Column(Integer, nullable=False, server_default="1")
    geometry = Column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = (
        UniqueConstraint("section_id", "track_code", name="uq_tracks_section_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id", ondelete="CASCADE"), nullable=False)
    track_code = Column(String(20), nullable=False)
    track_name = Column(String(100), nullable=True)
    direction = Column(String(20), nullable=True)
    track_type = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, server_default="ACTIVE")
    geometry = Column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=True)
