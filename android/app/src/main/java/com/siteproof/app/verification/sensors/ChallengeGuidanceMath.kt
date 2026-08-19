package com.siteproof.app.verification.sensors

import com.siteproof.app.verification.model.ChallengeSensorSample
import kotlin.math.abs
import kotlin.math.max

enum class ChallengeGuidanceStatus {
    WAITING,
    WRONG_DIRECTION,
    TOO_LITTLE,
    GOOD_RANGE,
    TOO_FAR,
}

data class ChallengeMovementGuidance(
    val signedDegrees: Double = 0.0,
    val progressFraction: Float = 0f,
    val status: ChallengeGuidanceStatus = ChallengeGuidanceStatus.WAITING,
)

object ChallengeGuidanceMath {
    private const val BASELINE_NS = 500_000_000L

    fun estimate(
        samples: List<ChallengeSensorSample>,
        challengeType: String,
        challengeStartRelativeNs: Long,
        targetDegrees: Double,
        minDegrees: Double,
        maxDegrees: Double,
    ): ChallengeMovementGuidance {
        val (axisIndex, expectedSign) = axisAndSign(challengeType)
        val gyro = samples
            .filter { it.type == "GYROSCOPE" && it.relativeTimestampNs >= challengeStartRelativeNs }
            .sortedBy { it.relativeTimestampNs }

        if (gyro.size < 2) return ChallengeMovementGuidance()

        val baselineEnd = challengeStartRelativeNs + BASELINE_NS
        val baseline = gyro
            .filter { it.relativeTimestampNs <= baselineEnd }
            .map { it.values.getOrElse(axisIndex) { 0.0 } }
        if (baseline.size < 2) return ChallengeMovementGuidance()

        val bias = baseline.average()
        val movement = gyro.filter { it.relativeTimestampNs >= baselineEnd }
        if (movement.size < 2) return ChallengeMovementGuidance()

        var radians = 0.0
        for ((left, right) in movement.zipWithNext()) {
            val dt = max(0.0, (right.relativeTimestampNs - left.relativeTimestampNs) / 1_000_000_000.0)
            val leftRate = left.values.getOrElse(axisIndex) { 0.0 } - bias
            val rightRate = right.values.getOrElse(axisIndex) { 0.0 } - bias
            radians += ((leftRate + rightRate) / 2.0) * dt
        }

        val signedDegrees = Math.toDegrees(radians) * expectedSign
        val safeTarget = max(targetDegrees, 1.0)
        val visibleProgress = (max(0.0, signedDegrees) / safeTarget).coerceIn(0.0, 1.0).toFloat()
        val status = when {
            abs(signedDegrees) < 3.0 -> ChallengeGuidanceStatus.WAITING
            signedDegrees <= -5.0 -> ChallengeGuidanceStatus.WRONG_DIRECTION
            signedDegrees < minDegrees * 0.85 -> ChallengeGuidanceStatus.TOO_LITTLE
            signedDegrees <= maxDegrees -> ChallengeGuidanceStatus.GOOD_RANGE
            else -> ChallengeGuidanceStatus.TOO_FAR
        }

        return ChallengeMovementGuidance(
            signedDegrees = signedDegrees,
            progressFraction = visibleProgress,
            status = status,
        )
    }

    private fun axisAndSign(challengeType: String): Pair<Int, Double> = when (challengeType) {
        "ROTATE_RIGHT" -> 1 to -1.0
        "ROTATE_LEFT" -> 1 to 1.0
        "TILT_DOWN" -> 0 to 1.0
        "TILT_UP" -> 0 to -1.0
        else -> 0 to 1.0
    }
}
