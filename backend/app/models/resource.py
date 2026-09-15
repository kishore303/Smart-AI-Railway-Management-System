from sqlalchemy import Column, BigInteger, String, Integer, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from app.database import Base


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint(
            "available_until IS NULL OR available_from IS NULL OR available_until > available_from",
            name="resources_available_check",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    resource_code = Column(String(30), nullable=False, unique=True)
    name = Column(String(150), nullable=True)
    department_id = Column(BigInteger, ForeignKey("departments.id"), nullable=False)
    resource_type = Column(String(50), nullable=True)
    quantity = Column(Integer, nullable=False, server_default="1")
    is_available = Column(Boolean, nullable=False, server_default="true")
    available_from = Column(DateTime(timezone=True), nullable=True)
    available_until = Column(DateTime(timezone=True), nullable=True)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
