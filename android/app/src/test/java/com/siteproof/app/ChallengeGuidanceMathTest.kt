package com.siteproof.app

import com.siteproof.app.verification.model.ChallengeSensorSample
import com.siteproof.app.verification.sensors.ChallengeGuidanceMath
import com.siteproof.app.verification.sensors.ChallengeGuidanceStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ChallengeGuidanceMathTest {
    private fun rotateRightSamples(rawSign: Double): List<ChallengeSensorSample> {
        val samples = mutableListOf<ChallengeSensorSample>()
        val stepNs = 20_000_000L
        val startNs = 100_000_000L
        for (index in 0..80) {
            val offset = index * stepNs
            val moving = offset >= 500_000_000L
            val rate = if (moving) rawSign * Math.toRadians(40.0) else 0.0
            samples += ChallengeSensorSample(
                type = "GYROSCOPE",
                relativeTimestampNs = startNs + offset,
                values = listOf(0.0, rate, 0.0),
                accuracy = 3,
            )
        }
        return samples
    }

    @Test
    fun rotateRightGoodRangeUsesBackendAxisAndSignConvention() {
        val result = ChallengeGuidanceMath.estimate(
            samples = rotateRightSamples(rawSign = -1.0),
            challengeType = "ROTATE_RIGHT",
            challengeStartRelativeNs = 100_000_000L,
            targetDegrees = 40.0,
            minDegrees = 28.0,
            maxDegrees = 54.0,
        )
        assertEquals(ChallengeGuidanceStatus.GOOD_RANGE, result.status)
        assertTrue(result.signedDegrees > 28.0)
        assertTrue(result.progressFraction > 0.7f)
    }

    @Test
    fun rotateRightOppositeMovementIsMarkedWrongDirection() {
        val result = ChallengeGuidanceMath.estimate(
            samples = rotateRightSamples(rawSign = 1.0),
            challengeType = "ROTATE_RIGHT",
            challengeStartRelativeNs = 100_000_000L,
            targetDegrees = 40.0,
            minDegrees = 28.0,
            maxDegrees = 54.0,
        )
        assertEquals(ChallengeGuidanceStatus.WRONG_DIRECTION, result.status)
        assertTrue(result.signedDegrees < -5.0)
    }
}
