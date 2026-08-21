package com.siteproof.app.verification.location

enum class LocationBoundaryDecision {
    INSIDE,
    OUTSIDE,
    INCONCLUSIVE,
}

object LocationBoundaryPolicy {
    fun classify(
        distanceMeters: Double,
        accuracyMeters: Double,
        allowedRadiusMeters: Double,
    ): LocationBoundaryDecision {
        require(distanceMeters >= 0.0)
        require(accuracyMeters >= 0.0)
        require(allowedRadiusMeters >= 0.0)
        val nearestPossibleDistance = (distanceMeters - accuracyMeters).coerceAtLeast(0.0)
        val farthestPossibleDistance = distanceMeters + accuracyMeters
        return when {
            farthestPossibleDistance <= allowedRadiusMeters -> LocationBoundaryDecision.INSIDE
            nearestPossibleDistance > allowedRadiusMeters -> LocationBoundaryDecision.OUTSIDE
            else -> LocationBoundaryDecision.INCONCLUSIVE
        }
    }
}
