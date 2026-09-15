from sqlalchemy import Column, BigInteger, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base


class WeatherReading(Base):
    __tablename__ = "weather_readings"
    __table_args__ = (
        CheckConstraint("section_id IS NOT NULL OR station_id IS NOT NULL", name="weather_readings_section_station_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=True)
    station_id = Column(BigInteger, ForeignKey("stations.id"), nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    temperature_c = Column(Numeric(5, 2), nullable=True)
    humidity_percent = Column(Numeric(5, 2), nullable=True)
    rainfall_mm = Column(Numeric(6, 2), nullable=True)
    wind_speed_kmph = Column(Numeric(6, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
