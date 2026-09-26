from sqlalchemy import Column, BigInteger, String, Integer, Numeric, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base


class Simulation(Base):
    __tablename__ = "simulations"
    __table_args__ = (
        CheckConstraint(
            "modified_end_time IS NULL OR modified_start_time IS NULL OR modified_end_time > modified_start_time",
            name="simulations_time_check",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    simulation_name = Column(String(150), nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    original_block_id = Column(BigInteger, ForeignKey("optimized_blocks.id"), nullable=True)
    modified_start_time = Column(DateTime(timezone=True), nullable=True)
    modified_end_time = Column(DateTime(timezone=True), nullable=True)
    additional_department_id = Column(BigInteger, ForeignKey("departments.id"), nullable=True)
    predicted_delay_mins = Column(Integer, nullable=True)
    affected_train_count = Column(Integer, nullable=True)
    ripple_impact_score = Column(Numeric(6, 3), nullable=True)
    optimization_score = Column(Numeric(6, 3), nullable=True)
    result_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
