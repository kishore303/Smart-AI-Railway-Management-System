from sqlalchemy import Column, BigInteger, String, DateTime, CheckConstraint, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.sql import func
from geoalchemy2 import Geometry  # noqa: F401 - keep import for ruff
from app.database import Base


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        CheckConstraint("code IN ('ENG','ELEC','SNT','OPS','CONTROL','RAILWAY','EMERGENCY')", name="departments_code_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(20), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DepartmentRole(Base):
    __tablename__ = "department_roles"

    department_id = Column(BigInteger, ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String, primary_key=True)  # user_role enum stored as string; DB type is user_role
