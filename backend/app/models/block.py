from sqlalchemy import Column, BigInteger, String, Integer, Numeric, DateTime, ForeignKey, CheckConstraint, Text, Boolean
from sqlalchemy.dialects.postgresql import ARRAY, ENUM as PGEnum
from sqlalchemy.sql import func
from app.database import Base


class BlockRequest(Base):
    __tablename__ = "block_requests"
    __table_args__ = (CheckConstraint("requested_end > requested_start", name="block_requests_window_check"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    block_code = Column(String(30), nullable=False, unique=True)
    maintenance_request_id = Column(BigInteger, ForeignKey("maintenance_requests.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=False)
    track_id = Column(BigInteger, ForeignKey("tracks.id"), nullable=True)
    requested_start = Column(DateTime(timezone=True), nullable=False)
    requested_end = Column(DateTime(timezone=True), nullable=False)
    block_type = Column(String(50), nullable=True)
    status = Column(PGEnum("REQUESTED","UNDER_REVIEW","PROPOSED","PENDING_APPROVAL","APPROVED","REJECTED","ACTIVE","COMPLETED","CANCELLED", name="block_request_status", create_type=False), nullable=False, server_default="REQUESTED")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BlockIntegrationRequest(Base):
    __tablename__ = "block_integration_requests"
    __table_args__ = (
        CheckConstraint("source_block_id <> target_block_id", name="block_integration_source_check"),
        CheckConstraint("requesting_department_id <> target_department_id", name="block_integration_dept_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_block_id = Column(BigInteger, ForeignKey("block_requests.id", ondelete="CASCADE"), nullable=False)
    target_block_id = Column(BigInteger, ForeignKey("block_requests.id", ondelete="CASCADE"), nullable=False)
    requesting_department_id = Column(BigInteger, ForeignKey("departments.id"), nullable=False)
    target_department_id = Column(BigInteger, ForeignKey("departments.id"), nullable=False)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=True)
    track_id = Column(BigInteger, ForeignKey("tracks.id"), nullable=True)
    overlap_start = Column(DateTime(timezone=True), nullable=True)
    overlap_end = Column(DateTime(timezone=True), nullable=True)
    overlap_duration_mins = Column(Integer, nullable=True)
    coordination_score = Column(Numeric(5, 2), nullable=True)
    detection_reason = Column(Text, nullable=True)
    spatial_status = Column(String(50), nullable=True)
    compatibility_status = Column(String(50), nullable=True)
    requested_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    response_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    response = Column(PGEnum("ACCEPT","REJECT","MODIFY", name="integration_response", create_type=False), nullable=True)
    reason = Column(Text, nullable=True)
    modified_start = Column(DateTime(timezone=True), nullable=True)
    modified_end = Column(DateTime(timezone=True), nullable=True)
    final_status = Column(PGEnum("PENDING","ACCEPTED","REJECTED","MODIFIED","APPROVED", name="integration_final_status", create_type=False), nullable=False, server_default="PENDING")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OptimizedBlock(Base):

    __tablename__ = "optimized_blocks"
    __table_args__ = (CheckConstraint("end_time > start_time", name="optimized_blocks_window_check"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    block_code = Column(String(30), nullable=False, unique=True)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=False)
    track_id = Column(BigInteger, ForeignKey("tracks.id"), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    total_duration_mins = Column(Integer, nullable=True)
    total_delay_mins = Column(Integer, nullable=True)
    affected_train_count = Column(Integer, nullable=True)
    ripple_impact_score = Column(Numeric(6, 3), nullable=True)
    resource_conflict_count = Column(Integer, nullable=False, server_default="0")
    combined_departments = Column(ARRAY(Text), nullable=True)
    optimization_score = Column(Numeric(6, 3), nullable=True)
    recommendation_reason = Column(Text, nullable=True)
    status = Column(PGEnum("PROPOSED","PENDING_APPROVAL","APPROVED","SCHEDULED","MODIFIED","REJECTED","ACTIVE","MAINTENANCE","CLEARANCE_PENDING","RELEASED","COMPLETED","CANCELLED", name="optimized_block_status", create_type=False), nullable=False, server_default="PROPOSED")
    approved_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    modified_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    modified_at = Column(DateTime(timezone=True), nullable=True)
    rejected_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BlockCandidate(Base):
    __tablename__ = "block_candidates"
    __table_args__ = (
        CheckConstraint("candidate_end > candidate_start", name="block_candidates_window_check"),
        CheckConstraint("safety_status IN ('FEASIBLE','INFEASIBLE','SAFE','UNSAFE')", name="block_candidates_safety_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    block_request_id = Column(BigInteger, ForeignKey("block_requests.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(BigInteger, ForeignKey("railway_sections.id"), nullable=False)
    track_id = Column(BigInteger, ForeignKey("tracks.id"), nullable=True)
    candidate_start = Column(DateTime(timezone=True), nullable=False)
    candidate_end = Column(DateTime(timezone=True), nullable=False)
    predicted_duration_mins = Column(Integer, nullable=True)
    predicted_delay_mins = Column(Integer, nullable=True)
    affected_train_count = Column(Integer, nullable=True)
    asset_risk_score = Column(Numeric(4, 3), nullable=True)
    safety_status = Column(String(12), nullable=False)
    safety_rejection_reason = Column(Text, nullable=True)
    optimization_score = Column(Numeric(6, 3), nullable=True)
    is_selected = Column(Boolean, nullable=False, server_default="false")
    selected_optimized_block_id = Column(BigInteger, ForeignKey("optimized_blocks.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OptimizedBlockSource(Base):
    __tablename__ = "optimized_block_sources"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    optimized_block_id = Column(BigInteger, ForeignKey("optimized_blocks.id", ondelete="CASCADE"), nullable=False)
    block_request_id = Column(BigInteger, ForeignKey("block_requests.id", ondelete="CASCADE"), nullable=False)


class BlockAffectedTrain(Base):
    __tablename__ = "block_affected_trains"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    block_id = Column(BigInteger, ForeignKey("optimized_blocks.id", ondelete="CASCADE"), nullable=False)
    train_id = Column(BigInteger, ForeignKey("trains.id"), nullable=False)
    predicted_delay_mins = Column(Integer, nullable=True)
    impact_level = Column(String, nullable=True)
    alternative_route_available = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BlockResourceAllocation(Base):
    __tablename__ = "block_resource_allocations"
    __table_args__ = (
        CheckConstraint("allocated_until > allocated_from", name="block_resource_time_check"),
        CheckConstraint("status IN ('ALLOCATED','RELEASED','CANCELLED')", name="block_resource_status_check"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    block_id = Column(BigInteger, ForeignKey("optimized_blocks.id", ondelete="CASCADE"), nullable=False)
    resource_id = Column(BigInteger, ForeignKey("resources.id"), nullable=False)
    quantity_required = Column(Integer, nullable=False, server_default="1")
    allocated_from = Column(DateTime(timezone=True), nullable=False)
    allocated_until = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, server_default="ALLOCATED")
