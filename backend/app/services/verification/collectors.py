from __future__ import annotations

from datetime import datetime, timezone
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.challenge import ChallengeResult, VerificationChallenge
from app.models.fusion import ConsistencyStatus, FusionAnalysisStatus, VisualInertialResult
from app.models.inspection import Inspection
from app.models.trust import VerificationSignalStatus, VerificationSignalType
from app.models.verification import VerificationSession
from app.models.visual_motion import VisualAnalysisStatus, VisualMotionResult
from app.services.verification.domain import VerificationSignal


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _status(score: float) -> VerificationSignalStatus:
    if score >= 0.80:
        return VerificationSignalStatus.PASS
    if score >= 0.55:
        return VerificationSignalStatus.PARTIAL
    return VerificationSignalStatus.FAIL


class SignalCollector:
    def __init__(self, db: Session, session: VerificationSession, inspection: Inspection):
        self.db = db
        self.session = session
        self.inspection = inspection
        self.settings = get_settings()
        self._terminal_cache: list[VerificationChallenge] | None = None

    def collect(self, required: frozenset[VerificationSignalType]) -> list[VerificationSignal]:
        builders = {
            VerificationSignalType.LOCATION: self._location,
            VerificationSignalType.SESSION_TIME: self._session_time,
            VerificationSignalType.CHALLENGE_COMPLETION: self._challenges,
            VerificationSignalType.SENSOR_QUALITY: self._sensor_quality,
            VerificationSignalType.VISUAL_MOTION: self._visual_motion,
            VerificationSignalType.SCENE_CONTINUITY: self._scene_continuity,
            VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY: self._fusion,
        }
        return [
            builders[signal_type](signal_type in required)
            for signal_type in VerificationSignalType
        ]

    def _unavailable(
        self,
        signal_type: VerificationSignalType,
        required: bool,
        reason: str,
        *,
        source_version: str | None = None,
    ) -> VerificationSignal:
        return VerificationSignal(
            type=signal_type,
            status=VerificationSignalStatus.UNAVAILABLE,
            score=0.0,
            confidence=0.0,
            available=False,
            required=required,
            reasons=[reason],
            metrics={},
            source_algorithm_version=source_version,
        )

    def _location(self, required: bool) -> VerificationSignal:
        location = self.session.pre_capture_location or {}
        distance = location.get("distanceMeters")
        radius = location.get("allowedRadiusMeters") or self.inspection.allowed_radius_meters
        accuracy = location.get("accuracy_meters")
        if accuracy is None:
            accuracy = location.get("accuracyMeters")
        if distance is None or radius is None or accuracy is None:
            return self._unavailable(
                VerificationSignalType.LOCATION,
                required,
                "Capture location evidence was unavailable.",
                source_version="location-v1",
            )

        distance = float(distance)
        radius = max(float(radius), 1.0)
        accuracy = max(float(accuracy), 0.0)
        clearly_outside = distance - accuracy > radius
        unusable_accuracy = accuracy > max(300.0, radius * 3.0)
        borderline = not clearly_outside and distance + accuracy > radius
        confidence = max(0.15, _clamp(1.0 - accuracy / max(radius * 2.0, 60.0)))

        metrics = {
            "distanceMeters": round(distance, 2),
            "allowedRadiusMeters": round(radius, 2),
            "accuracyMeters": round(accuracy, 2),
            "clearlyOutside": clearly_outside,
            "borderline": borderline,
        }
        if unusable_accuracy:
            return VerificationSignal(
                type=VerificationSignalType.LOCATION,
                status=VerificationSignalStatus.INCONCLUSIVE,
                score=0.50,
                confidence=min(confidence, 0.35),
                available=True,
                required=required,
                reasons=[
                    "GPS uncertainty was too large to make a reliable location determination."
                ],
                metrics=metrics,
                source_algorithm_version="location-v1",
            )
        if clearly_outside:
            return VerificationSignal(
                type=VerificationSignalType.LOCATION,
                status=VerificationSignalStatus.FAIL,
                score=0.0,
                confidence=max(0.80, confidence),
                available=True,
                required=required,
                reasons=[
                    f"Capture was approximately {distance:.0f} m from the required site, "
                    f"outside the {radius:.0f} m radius."
                ],
                metrics=metrics,
                source_algorithm_version="location-v1",
            )
        if borderline:
            score = 0.65
            status = VerificationSignalStatus.PARTIAL
            reason = "Capture location was near the permitted boundary given GPS uncertainty."
        else:
            score = max(0.85, 1.0 - 0.15 * min(1.0, distance / radius))
            status = VerificationSignalStatus.PASS
            reason = f"Capture location was within {distance:.0f} m of the required site."
        return VerificationSignal(
            type=VerificationSignalType.LOCATION,
            status=status,
            score=score,
            confidence=max(0.50, confidence),
            available=True,
            required=required,
            reasons=[reason],
            metrics=metrics,
            source_algorithm_version="location-v1",
        )

    def _session_time(self, required: bool) -> VerificationSignal:
        if self.session.capture_started_at is None or self.session.capture_ended_at is None:
            return self._unavailable(
                VerificationSignalType.SESSION_TIME,
                required,
                "Capture timing evidence was incomplete.",
                source_version="session-time-v1",
            )
        deadline_value = (self.session.site_snapshot or {}).get("deadline")
        deadline = (
            _aware(datetime.fromisoformat(str(deadline_value)))
            if deadline_value
            else _aware(self.inspection.deadline)
        )
        capture_start = _aware(self.session.capture_started_at)
        capture_end = _aware(self.session.capture_ended_at)
        monotonic = capture_end >= capture_start
        before_deadline = capture_start <= deadline
        clock_offset = abs(float(self.session.clock_offset_ms or 0.0))
        offset_ok = clock_offset <= 120_000.0
        score = fmean(
            [
                1.0 if monotonic else 0.0,
                1.0 if before_deadline else 0.0,
                1.0 if offset_ok else 0.6,
            ]
        )
        reasons: list[str] = []
        if monotonic and before_deadline:
            reasons.append("Capture timing was monotonic and began before the inspection deadline.")
        if not before_deadline:
            reasons.append("Capture began after the configured inspection deadline.")
        if not monotonic:
            reasons.append("Capture timestamps were not monotonic.")
        if not offset_ok:
            reasons.append("Client/server wall-clock offset was unusually large.")
        return VerificationSignal(
            type=VerificationSignalType.SESSION_TIME,
            status=_status(score),
            score=score,
            confidence=0.90 if monotonic else 0.65,
            available=True,
            required=required,
            reasons=reasons,
            metrics={
                "captureStartedAt": capture_start.isoformat(),
                "captureEndedAt": capture_end.isoformat(),
                "deadline": deadline.isoformat(),
                "clockOffsetMs": round(clock_offset, 1),
                "monotonic": monotonic,
                "beforeDeadline": before_deadline,
            },
            source_algorithm_version="session-time-v1",
        )

    def _terminal_challenges(self) -> list[VerificationChallenge]:
        if self._terminal_cache is not None:
            return self._terminal_cache
        rows = list(
            self.db.scalars(
                select(VerificationChallenge)
                .where(VerificationChallenge.session_id == self.session.id)
                .order_by(
                    VerificationChallenge.sequence_number,
                    VerificationChallenge.attempt_number,
                )
            ).all()
        )
        latest: dict[int, VerificationChallenge] = {}
        for row in rows:
            current = latest.get(row.sequence_number)
            if current is None or row.attempt_number > current.attempt_number:
                latest[row.sequence_number] = row
        self._terminal_cache = [latest[key] for key in sorted(latest)]
        return self._terminal_cache

    def _challenges(self, required: bool) -> VerificationSignal:
        rows = self._terminal_challenges()
        if not rows:
            return self._unavailable(
                VerificationSignalType.CHALLENGE_COMPLETION,
                required,
                "No randomized challenge results were available.",
                source_version="challenge-v1",
            )
        contributions: list[float] = []
        confidences: list[float] = []
        pass_count = fail_count = inconclusive_count = high_conf_failures = 0
        retry_count = sum(max(0, row.attempt_number - 1) for row in rows)
        for row in rows:
            score = float(row.validation_score or 0.0)
            confidence = float(row.sensor_score or 0.0)
            confidences.append(confidence)
            if row.result == ChallengeResult.PASS:
                pass_count += 1
                contributions.append(score)
            elif row.result == ChallengeResult.FAIL:
                fail_count += 1
                contributions.append(0.0)
                if confidence >= 0.80:
                    high_conf_failures += 1
            else:
                inconclusive_count += 1
                contributions.append(min(0.45, score * 0.5))
        score = fmean(contributions)
        confidence = fmean(confidences) if confidences else 0.0
        status = (
            VerificationSignalStatus.PASS
            if fail_count == 0 and inconclusive_count == 0 and score >= 0.75
            else VerificationSignalStatus.FAIL
            if fail_count >= 2
            else VerificationSignalStatus.PARTIAL
        )
        reason = (
            f"{pass_count} of {len(rows)} terminal randomized challenges passed."
            if status == VerificationSignalStatus.PASS
            else f"Terminal challenges produced {pass_count} pass, {fail_count} fail, "
            f"{inconclusive_count} inconclusive result(s)."
        )
        return VerificationSignal(
            type=VerificationSignalType.CHALLENGE_COMPLETION,
            status=status,
            score=_clamp(score),
            confidence=_clamp(confidence),
            available=True,
            required=required,
            reasons=[reason],
            metrics={
                "total": len(rows),
                "passed": pass_count,
                "failed": fail_count,
                "inconclusive": inconclusive_count,
                "retryCount": retry_count,
                "highConfidenceFailures": high_conf_failures,
            },
            source_algorithm_version="challenge-v1",
        )

    def _sensor_quality(self, required: bool) -> VerificationSignal:
        rows = self._terminal_challenges()
        if not rows:
            return self._unavailable(
                VerificationSignalType.SENSOR_QUALITY,
                required,
                "No Phase 4 sensor-quality results were available.",
                source_version="sensor-v1",
            )
        scores = [float(row.sensor_score or 0.0) for row in rows]
        gyro_good = 0
        max_gaps: list[float] = []
        for row in rows:
            quality = row.sensor_quality_json or {}
            gyro = quality.get("gyroscope") or quality.get("GYROSCOPE") or {}
            if str(gyro.get("quality") or "").upper() == "GOOD":
                gyro_good += 1
            gap = gyro.get("maxGapMs")
            if isinstance(gap, (int, float)):
                max_gaps.append(float(gap))
        score = fmean(scores)
        gyro_fraction = gyro_good / len(rows) if gyro_good else 0.0
        confidence = _clamp(0.75 * score + 0.25 * gyro_fraction)
        return VerificationSignal(
            type=VerificationSignalType.SENSOR_QUALITY,
            status=_status(score),
            score=_clamp(score),
            confidence=confidence,
            available=True,
            required=required,
            reasons=[
                "Required motion sensors supplied usable evidence."
                if score >= 0.80
                else "Sensor quality or sensor-to-sensor agreement was degraded."
            ],
            metrics={
                "challengeCount": len(rows),
                "goodGyroscopeWindows": gyro_good,
                "maxGapMs": max(max_gaps) if max_gaps else None,
                "gyroscopeAvailable": bool(
                    (self.session.device_capabilities or {}).get("gyroscope")
                ),
                "rotationVectorAvailable": bool(
                    (self.session.device_capabilities or {}).get("rotation_vector")
                ),
            },
            source_algorithm_version="sensor-v1",
        )

    def _terminal_ids(self) -> set:
        return {row.id for row in self._terminal_challenges()}

    def _visual_rows(self) -> list[VisualMotionResult]:
        terminal_ids = self._terminal_ids()
        if not terminal_ids:
            return []
        return list(
            self.db.scalars(
                select(VisualMotionResult).where(
                    VisualMotionResult.session_id == self.session.id,
                    VisualMotionResult.analysis_version == self.settings.vision_analysis_version,
                    VisualMotionResult.challenge_id.in_(terminal_ids),
                )
            ).all()
        )

    def _visual_motion(self, required: bool) -> VerificationSignal:
        rows = self._visual_rows()
        expected = len(self._terminal_challenges())
        if not rows or len(rows) < expected:
            return self._unavailable(
                VerificationSignalType.VISUAL_MOTION,
                required,
                "Phase 5 terminal visual-motion analysis was unavailable.",
                source_version=self.settings.vision_analysis_version,
            )
        if any(
            row.analysis_status in {VisualAnalysisStatus.PENDING, VisualAnalysisStatus.PROCESSING}
            for row in rows
        ):
            return VerificationSignal(
                type=VerificationSignalType.VISUAL_MOTION,
                status=VerificationSignalStatus.INCONCLUSIVE,
                score=0.0,
                confidence=0.0,
                available=True,
                required=required,
                reasons=["Visual-motion analysis is still processing."],
                metrics={"processing": True},
                source_algorithm_version=self.settings.vision_analysis_version,
            )
        successes = [row for row in rows if row.analysis_status == VisualAnalysisStatus.SUCCESS]
        failed = [row for row in rows if row.analysis_status == VisualAnalysisStatus.FAILED]
        inconclusive = [
            row for row in rows if row.analysis_status == VisualAnalysisStatus.INCONCLUSIVE
        ]
        confidence = fmean([float(row.visual_confidence) for row in rows])
        usable_fraction = len(successes) / len(rows)
        score = _clamp(0.65 * usable_fraction + 0.35 * confidence)
        status = (
            VerificationSignalStatus.INCONCLUSIVE
            if not successes and (failed or inconclusive)
            else _status(score)
        )
        return VerificationSignal(
            type=VerificationSignalType.VISUAL_MOTION,
            status=status,
            score=score,
            confidence=_clamp(confidence),
            available=True,
            required=required,
            reasons=[
                f"Camera motion was reliably estimated for {len(successes)} of "
                f"{len(rows)} terminal challenge(s)."
            ],
            metrics={
                "challengeCount": len(rows),
                "successful": len(successes),
                "inconclusive": len(inconclusive),
                "failed": len(failed),
                "meanVisualConfidence": round(confidence, 4),
                "meanInlierRatio": round(fmean([row.inlier_ratio for row in rows]), 4),
            },
            source_algorithm_version=self.settings.vision_analysis_version,
        )

    def _scene_continuity(self, required: bool) -> VerificationSignal:
        rows = self._visual_rows()
        if not rows:
            return self._unavailable(
                VerificationSignalType.SCENE_CONTINUITY,
                required,
                "Scene-continuity metrics were unavailable.",
                source_version=self.settings.vision_analysis_version,
            )
        continuity = fmean([float(row.scene_continuity_score) for row in rows])
        duplicate = max(float(row.duplicate_frame_ratio) for row in rows)
        invalid = max(float(row.invalid_frame_ratio) for row in rows)
        freeze_ms = max(int(row.freeze_duration_ms) for row in rows)
        major = continuity < 0.40 or freeze_ms >= 2000 or duplicate >= 0.50
        score = _clamp(
            0.70 * continuity
            + 0.15 * (1.0 - duplicate)
            + 0.15 * (1.0 - invalid)
        )
        confidence = _clamp(fmean([float(row.visual_confidence) for row in rows]))
        return VerificationSignal(
            type=VerificationSignalType.SCENE_CONTINUITY,
            status=VerificationSignalStatus.FAIL if major else _status(score),
            score=score,
            confidence=confidence,
            available=True,
            required=required,
            reasons=[
                "No major scene-continuity anomaly was detected."
                if not major
                else "A major scene-continuity anomaly was detected during challenge video."
            ],
            metrics={
                "meanContinuityScore": round(continuity, 4),
                "maxDuplicateFrameRatio": round(duplicate, 4),
                "maxInvalidFrameRatio": round(invalid, 4),
                "maxFreezeDurationMs": freeze_ms,
                "majorDiscontinuity": major,
            },
            source_algorithm_version=self.settings.vision_analysis_version,
        )

    def _fusion(self, required: bool) -> VerificationSignal:
        terminal_ids = self._terminal_ids()
        rows = list(
            self.db.scalars(
                select(VisualInertialResult).where(
                    VisualInertialResult.session_id == self.session.id,
                    VisualInertialResult.fusion_version == self.settings.fusion_analysis_version,
                    VisualInertialResult.challenge_id.in_(terminal_ids),
                )
            ).all()
        ) if terminal_ids else []
        expected = len(self._terminal_challenges())
        if not rows or len(rows) < expected:
            return self._unavailable(
                VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY,
                required,
                "Phase 6 terminal visual-inertial consistency analysis was unavailable.",
                source_version=self.settings.fusion_analysis_version,
            )
        if any(row.analysis_status != FusionAnalysisStatus.COMPLETE for row in rows):
            return VerificationSignal(
                type=VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY,
                status=VerificationSignalStatus.INCONCLUSIVE,
                score=0.0,
                confidence=0.0,
                available=True,
                required=required,
                reasons=["Visual-inertial fusion has not completed for every terminal challenge."],
                metrics={"processing": True},
                source_algorithm_version=self.settings.fusion_analysis_version,
            )
        scores = [
            float(
                row.effective_consistency_score
                if row.effective_consistency_score is not None
                else row.raw_consistency_score or 0.0
            )
            for row in rows
        ]
        confidences = [float(row.fusion_confidence or 0.0) for row in rows]
        score = _clamp(fmean(scores))
        confidence = _clamp(fmean(confidences))
        mismatches = [row for row in rows if row.consistency_status == ConsistencyStatus.MISMATCH]
        inconclusive = [
            row for row in rows if row.consistency_status == ConsistencyStatus.INCONCLUSIVE
        ]
        partial = [
            row
            for row in rows
            if row.consistency_status == ConsistencyStatus.PARTIALLY_CONSISTENT
        ]
        strong_mismatch = any(
            row.consistency_status == ConsistencyStatus.MISMATCH
            and float(row.fusion_confidence or 0.0) >= 0.80
            for row in rows
        )
        if strong_mismatch:
            status = VerificationSignalStatus.FAIL
        elif inconclusive:
            status = VerificationSignalStatus.INCONCLUSIVE
        elif mismatches or partial:
            status = VerificationSignalStatus.PARTIAL
        else:
            status = VerificationSignalStatus.PASS
        if status == VerificationSignalStatus.PASS:
            reasons = ["Camera movement and physical phone movement were mutually consistent."]
        elif status == VerificationSignalStatus.PARTIAL:
            reasons = [
                f"Cross-signal analysis found {len(partial)} partial and "
                f"{len(mismatches)} mismatch terminal challenge(s)."
            ]
        else:
            reasons = [
                f"Cross-signal analysis found {len(mismatches)} mismatch and "
                f"{len(inconclusive)} inconclusive terminal challenge(s)."
            ]
        mismatch_reasons = sorted(
            {
                reason
                for row in rows
                for reason in (row.mismatch_reasons_json or [])
            }
        )
        consistency_status = (
            "MISMATCH"
            if strong_mismatch
            else "INCONCLUSIVE"
            if inconclusive
            else "PARTIALLY_CONSISTENT"
            if status == VerificationSignalStatus.PARTIAL
            else "CONSISTENT"
        )
        return VerificationSignal(
            type=VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY,
            status=status,
            score=score,
            confidence=confidence,
            available=True,
            required=required,
            reasons=reasons,
            metrics={
                "challengeCount": len(rows),
                "consistentCount": sum(
                    row.consistency_status == ConsistencyStatus.CONSISTENT for row in rows
                ),
                "partialCount": len(partial),
                "mismatchCount": len(mismatches),
                "inconclusiveCount": len(inconclusive),
                "consistencyStatus": consistency_status,
                "mismatchReasons": mismatch_reasons,
                "meanConsistencyScore": round(score, 4),
            },
            source_algorithm_version=self.settings.fusion_analysis_version,
        )
