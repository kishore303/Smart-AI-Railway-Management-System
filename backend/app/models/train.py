from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base


class Train(Base):
    __tablename__ = "trains"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    train_number = Column(String(20), nullable=False, unique=True)
    train_name = Column(String(150), nullable=True)
    train_type = Column(String(30), nullable=True)
    priority = Column(String(20), nullable=True)
    source_station_id = Column(BigInteger, ForeignKey("stations.id"), nullable=True)
    destination_station_id = Column(BigInteger, ForeignKey("stations.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TrainSchedule(Base):
    __tablename__ = "train_schedules"
    __table_args__ = (
        CheckConstraint("exit_time > entry_time", name="train_schedules_time_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    train_id = Column(BigInteger, ForeignKey("trains.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=False)
    track_id = Column(BigInteger, ForeignKey("tracks.id"), nullable=True)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=False)
    direction = Column(String(20), nullable=True)
    scheduled_delay_mins = Column(Integer, nullable=False, server_default="0")
