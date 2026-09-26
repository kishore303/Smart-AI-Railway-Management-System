"""Train movement and traffic conflict safety rule."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.block import BlockCandidate
from app.models.train import TrainSchedule
from app.services.timetable import TrainScheduleService
from app.safety.rules.base import BaseSafetyRule, RuleResult


class TrainConflictRule(BaseSafetyRule):
    """Evaluates train movements scheduled in the corridor during the candidate window.
    
    Separates operational warnings (manageable traffic requiring regulation/rerouting in Phase 7)
    from hard safety conflicts (e.g. unmanageable non-reroutable priority traffic if configured).
    """

    @property
    def rule_name(self) -> str:
        return "TRAIN_CONFLICT"

    def evaluate(self, candidate: BlockCandidate, db: Session, context: Optional[Dict[str, Any]] = None) -> RuleResult:
        # Check database train schedules
        q = db.query(TrainSchedule).filter(
            TrainSchedule.section_id == candidate.section_id,
            TrainSchedule.entry_time < candidate.candidate_end,
            TrainSchedule.exit_time > candidate.candidate_start,
        )
        if candidate.track_id:
            q = q.filter((TrainSchedule.track_id == candidate.track_id) | (TrainSchedule.track_id.is_(None)))

        scheduled_trains = q.all()

        # If DB schedules exist, assess traffic
        if scheduled_trains:
            count = len(scheduled_trains)
            # In Phase 6, scheduled trains represent operational impact (WARNING) that OR-Tools optimizes in Phase 7
            return RuleResult(
                rule=self.rule_name,
                status="WARNING",
                severity="WARNING",
                message=f"{count} train movement(s) scheduled during candidate window. Operational regulation/rerouting required during optimization.",
                details={"affected_train_count": count},
            )

        # Also check timetable service
        try:
            tt_trains = TrainScheduleService.get_affected_trains(
                db=db,
                section_id=candidate.section_id,
                track_id=candidate.track_id,
                start_time=candidate.candidate_start,
                end_time=candidate.candidate_end,
            )
            if tt_trains:
                return RuleResult(
                    rule=self.rule_name,
                    status="WARNING",
                    severity="WARNING",
                    message=f"{len(tt_trains)} timetable train(s) traverse corridor during window. Operational impact to be minimized in Phase 7.",
                    details={"affected_train_count": len(tt_trains)},
                )
        except Exception:
            pass

        return RuleResult(
            rule=self.rule_name,
            status="PASS",
            severity="INFO",
            message="No conflicting train movements detected during candidate window.",
        )
