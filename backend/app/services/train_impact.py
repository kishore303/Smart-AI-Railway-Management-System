"""Train Impact Service.

Combines Railway Timetable affected train identification with the TrainDelayPredictor.
Runs individual train delay predictions separately and aggregates overall operational impact.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.timetable import TrainScheduleService
from app.ml.predictors.train_delay import TrainDelayPredictor


class TrainImpactService:
    """Orchestrates timetable train queries and individual delay model predictions."""

    def __init__(self):
        self.delay_predictor = TrainDelayPredictor()

    def assess_train_impact(
        self,
        db: Session,
        section_id: int,
        track_id: Optional[int],
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """
        Identify affected trains via Timetable Service and predict individual delays.
        Aggregates total, average, and maximum delay metrics.
        """
        affected_trains = TrainScheduleService.get_affected_trains(
            db=db,
            section_id=section_id,
            track_id=track_id,
            start_time=start_time,
            end_time=end_time,
        )

        if not affected_trains:
            return {
                "affected_train_count": 0,
                "total_predicted_delay_minutes": 0.0,
                "average_predicted_delay_minutes": 0.0,
                "maximum_predicted_delay_minutes": 0.0,
                "train_impact_score": 0.0,
                "impact_level": "NONE",
                "individual_predictions": [],
                "model_name": self.delay_predictor.model_name,
                "model_version": self.delay_predictor.model_version,
            }

        individual_results: List[Dict[str, Any]] = []
        delays: List[float] = []

        for train_rec in affected_trains:
            # Prepare feature dictionary for individual delay model
            feat = {
                "train_number": train_rec["train_number"],
                "train_name": train_rec["train_name"],
                "station_code": train_rec["station_code"],
                "station_name": train_rec["station_name"],
                "pct_right_time": train_rec.get("pct_right_time", 80.0),
                "pct_slight_delay": train_rec.get("pct_slight_delay", 15.0),
                "pct_significant_delay": train_rec.get("pct_significant_delay", 4.0),
                "pct_cancelled_unknown": train_rec.get("pct_cancelled_unknown", 1.0),
            }

            pred = self.delay_predictor.predict(feat)
            delay = pred["predicted_delay_mins"]
            delays.append(delay)

            individual_results.append({
                "train_number": train_rec["train_number"],
                "train_name": train_rec["train_name"],
                "station_code": train_rec["station_code"],
                "station_name": train_rec["station_name"],
                "section_id": section_id,
                "track_id": train_rec.get("track_id"),
                "scheduled_entry": train_rec.get("scheduled_entry"),
                "scheduled_exit": train_rec.get("scheduled_exit"),
                "predicted_delay_mins": delay,
                "predicted_delay_minutes": delay,
                "impact_level": pred["impact_level"],
                "impact_reason": train_rec.get("impact_reason"),
            })

        total_delay = sum(delays)
        avg_delay = total_delay / len(delays) if delays else 0.0
        max_delay = max(delays) if delays else 0.0

        # Overall composite train impact score (0.0 to 1.0)
        if total_delay < 30.0:
            impact_level = "LOW"
            impact_score = min(0.35, total_delay / 100.0)
        elif total_delay < 90.0:
            impact_level = "MEDIUM"
            impact_score = 0.55
        elif total_delay < 180.0:
            impact_level = "HIGH"
            impact_score = 0.80
        else:
            impact_level = "CRITICAL"
            impact_score = 1.0

        return {
            "affected_train_count": len(individual_results),
            "total_predicted_delay_minutes": round(total_delay, 1),
            "average_predicted_delay_minutes": round(avg_delay, 1),
            "maximum_predicted_delay_minutes": round(max_delay, 1),
            "train_impact_score": round(impact_score, 3),
            "impact_level": impact_level,
            "individual_predictions": individual_results,
            "model_name": self.delay_predictor.model_name,
            "model_version": self.delay_predictor.model_version,
        }
