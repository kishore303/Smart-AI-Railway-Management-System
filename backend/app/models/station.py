from sqlalchemy import Column, BigInteger, String, Numeric, DateTime
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from app.database import Base


class Station(Base):
    __tablename__ = "stations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    code = Column(String(20), nullable=False, unique=True)
    zone = Column(String(50), nullable=True)
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
