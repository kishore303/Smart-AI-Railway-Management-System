"""Block Candidate Generation Service.

Takes verified maintenance requests, Phase 5 ML predictions, and operational availability windows,
generates multiple feasible candidate windows using configurable time granularity intervals (15/30/60m),
and automatically validates each candidate via the deterministic Safety Engine.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models.block import BlockRequest, BlockCandidate
from app.models.maintenance import MaintenanceRequest, MaintenancePrediction
from app.models.audit import AuditLog
from app.safety.engine import validate_candidate
from app.services.train_impact import TrainImpactService


class CandidateGeneratorService:
    """Service generating operational candidate block windows and executing safety validation."""

    def __init__(self):
        self.impact_service = TrainImpactService()

    def generate_candidates_for_block(
        self,
        db: Session,
        block_request_id: int,
        user_id: Optional[int] = None,
        interval_mins: int = 30,
        max_candidates: int = 5,
        min_duration_buffer_mins: int = 0,
        window_days: int = 1,
    ) -> Dict[str, Any]:
        """
        Generate candidate block windows for a block request.
        Granularity interval (15, 30, 60m) is configurable.
        """
        block = db.query(BlockRequest).filter(BlockRequest.id == block_request_id).first()
        if not block:
            raise ValueError(f"Block request #{block_request_id} not found")

        mreq = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == block.maintenance_request_id).first()
        if not mreq:
            raise ValueError(f"Associated maintenance request not found for block #{block_request_id}")

        # 1. Fetch Phase 5 predicted metrics if available
        pred = (
            db.query(MaintenancePrediction)
            .filter(MaintenancePrediction.maintenance_request_id == mreq.id)
            .order_by(MaintenancePrediction.predicted_at.desc())
            .first()
        )

        base_duration = (
            pred.predicted_duration_mins
            if (pred and pred.predicted_duration_mins)
            else (mreq.requested_duration_mins or 120)
        )
        total_duration_mins = base_duration + min_duration_buffer_mins
        risk_score = pred.asset_risk_score if pred else 0.25

        # 2. Window bounds
        window_start = block.requested_start
        window_end = block.requested_end
        avail_duration_mins = int((window_end - window_start).total_seconds() // 60)

        step_mins = max(15, interval_mins)
        generated_windows = []

        # Case A: Sliding windows within availability range
        if avail_duration_mins >= total_duration_mins:
            curr_start = window_start
            while curr_start + timedelta(minutes=total_duration_mins) <= window_end and len(generated_windows) < max_candidates:
                curr_end = curr_start + timedelta(minutes=total_duration_mins)
                generated_windows.append((curr_start, curr_end))
                curr_start += timedelta(minutes=step_mins)

        # Case B: If not enough candidates within range or range is narrow, generate multi-day / shifted slots
        if len(generated_windows) < max_candidates:
            for day_offset in range(1, window_days + 1):
                if len(generated_windows) >= max_candidates:
                    break
                shift = timedelta(days=day_offset)
                curr_start = window_start + shift
                curr_end = curr_start + timedelta(minutes=total_duration_mins)
                generated_windows.append((curr_start, curr_end))

        # 3. Create and validate BlockCandidate records
        results = []
        for cand_start, cand_end in generated_windows:
            # Assess train impact for this candidate window
            impact = self.impact_service.assess_train_impact(
                db=db,
                section_id=block.section_id,
                track_id=block.track_id,
                start_time=cand_start,
                end_time=cand_end,
            )

            candidate = BlockCandidate(
                block_request_id=block.id,
                section_id=block.section_id,
                track_id=block.track_id,
                candidate_start=cand_start,
                candidate_end=cand_end,
                predicted_duration_mins=total_duration_mins,
                predicted_delay_mins=int(round(impact.get("total_predicted_delay_minutes", 0.0))),
                affected_train_count=impact.get("affected_train_count", 0),
                asset_risk_score=risk_score,
                safety_status="FEASIBLE",  # will be updated by validate_candidate
                optimization_score=None,
                is_selected=False,
                created_at=datetime.now(timezone.utc),
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)

            # 4. Run Safety Engine validation
            safety_res = validate_candidate(candidate, db, user_id=user_id, persist=True)

            duration_mins = int((cand_end - cand_start).total_seconds() // 60)
            results.append({
                "id": candidate.id,
                "candidate_id": candidate.id,
                "block_request_id": block.id,
                "section_id": block.section_id,
                "track_id": block.track_id,
                "candidate_start": cand_start.isoformat(),
                "candidate_end": cand_end.isoformat(),
                "duration_minutes": duration_mins,
                "predicted_duration_mins": total_duration_mins,
                "predicted_delay_mins": candidate.predicted_delay_mins,
                "affected_train_count": candidate.affected_train_count,
                "asset_risk_score": float(risk_score) if risk_score is not None else None,
                "safety_status": safety_res["overall_status"],
                "is_safe_for_optimization": safety_res["is_safe_for_optimization"],
                "safety_rejection_reason": candidate.safety_rejection_reason,
                "rejection_reasons": safety_res["rejection_reasons"],
                "warnings": safety_res["warnings"],
                "checks": safety_res["checks"],
                "is_selected": False,
                "created_at": candidate.created_at.isoformat(),
            })

        # 5. Audit Logging
        if user_id:
            safe_count = sum(1 for r in results if r["is_safe_for_optimization"])
            audit = AuditLog(
                user_id=user_id,
                action="GENERATE_CANDIDATES",
                entity_type="block_request",
                entity_id=block.id,
                description=f"Generated {len(results)} candidate windows (interval={interval_mins}m): {safe_count} SAFE, {len(results)-safe_count} UNSAFE",
            )
            db.add(audit)
            db.commit()

        safe_total = sum(1 for r in results if r["is_safe_for_optimization"])
        return {
            "block_id": block.id,
            "block_request_id": block.id,
            "generated": len(results),
            "total_candidates": len(results),
            "safe_candidates_count": safe_total,
            "safe_count": safe_total,
            "unsafe_candidates_count": len(results) - safe_total,
            "unsafe_count": len(results) - safe_total,
            "interval_minutes": interval_mins,
            "message": f"Generated {len(results)} block candidates ({safe_total} SAFE for optimization).",
            "candidates": results,
        }
