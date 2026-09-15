from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey, CheckConstraint, Text
from sqlalchemy.sql import func
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "recipient_user_id IS NOT NULL OR recipient_department_id IS NOT NULL",
            name="notifications_recipient_check",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    recipient_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    recipient_department_id = Column(BigInteger, ForeignKey("departments.id"), nullable=True)
    type = Column(String, nullable=False)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=True)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=True)
    track_id = Column(BigInteger, ForeignKey("tracks.id"), nullable=True)
    block_request_id = Column(BigInteger, ForeignKey("block_requests.id"), nullable=True)
    optimized_block_id = Column(BigInteger, ForeignKey("optimized_blocks.id"), nullable=True)
    integration_request_id = Column(BigInteger, ForeignKey("block_integration_requests.id"), nullable=True)
    priority = Column(String, nullable=False, server_default="NORMAL")
    is_read = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
