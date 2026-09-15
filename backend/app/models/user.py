from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Index
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        ForeignKeyConstraint(
            ["department_id", "role"],
            ["department_roles.department_id", "department_roles.role"],
            name="fk_users_department_role",
        ),
        Index("idx_users_department", "department_id"),
        Index("idx_users_role", "role"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        PGEnum(
            "MAINTENANCE_STAFF",
            "ENGINEER_REVIEWER",
            "OPERATOR",
            "CONTROLLER",
            "AUTHORIZED_OFFICIAL",
            "EMERGENCY_OPERATOR",
            name="user_role",
            create_type=False,
        ),
        nullable=False,
    )
    department_id = Column(BigInteger, ForeignKey("departments.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
