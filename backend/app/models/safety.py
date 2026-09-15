from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class SafetyValidation(Base):
    __tablename__ = "safety_validations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id = Column(BigInteger, ForeignKey("block_candidates.id", ondelete="CASCADE"), nullable=False, unique=True)
    block_request_id = Column(BigInteger, ForeignKey("block_requests.id", ondelete="CASCADE"), nullable=False)
    overall_status = Column(String(10), nullable=False)  # SAFE / UNSAFE
    is_safe_for_optimization = Column(Boolean, nullable=False)
    checks = Column(JSONB, nullable=False)  # list of {check,status,reason,severity}
    rejection_reasons = Column(JSONB, nullable=True)  # list of strings
    warnings = Column(JSONB, nullable=True)
    validated_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
