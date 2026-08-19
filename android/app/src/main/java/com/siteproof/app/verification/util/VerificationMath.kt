package com.siteproof.app.verification.util

import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

object VerificationMath {
    fun relativeTimestampNs(eventTimestampNs: Long, captureStartNs: Long): Long {
        require(eventTimestampNs >= captureStartNs) { "Event timestamp predates capture start" }
        return eventTimestampNs - captureStartNs
    }

    fun haversineMeters(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val radius = 6_371_000.0
        val phi1 = Math.toRadians(lat1)
        val phi2 = Math.toRadians(lat2)
        val dPhi = Math.toRadians(lat2 - lat1)
        val dLambda = Math.toRadians(lon2 - lon1)
        val a = sin(dPhi / 2) * sin(dPhi / 2) +
            cos(phi1) * cos(phi2) * sin(dLambda / 2) * sin(dLambda / 2)
        return 2 * radius * atan2(sqrt(a), sqrt(1 - a))
    }

    fun accuracyLabel(accuracyMeters: Double): String = when {
        accuracyMeters <= 20.0 -> "Good"
        accuracyMeters <= 50.0 -> "Moderate"
        else -> "Poor"
    }
}
