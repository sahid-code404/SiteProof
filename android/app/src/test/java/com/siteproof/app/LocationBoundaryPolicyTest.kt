package com.siteproof.app

import com.siteproof.app.verification.location.LocationBoundaryDecision
import com.siteproof.app.verification.location.LocationBoundaryPolicy
import org.junit.Assert.assertEquals
import org.junit.Test

class LocationBoundaryPolicyTest {
    @Test
    fun preciseFixWhollyInsideRadiusPasses() {
        assertEquals(
            LocationBoundaryDecision.INSIDE,
            LocationBoundaryPolicy.classify(30.0, 20.0, 100.0),
        )
    }

    @Test
    fun veryInaccurateFixCenteredInsideIsInconclusive() {
        assertEquals(
            LocationBoundaryDecision.INCONCLUSIVE,
            LocationBoundaryPolicy.classify(30.0, 900.0, 100.0),
        )
    }

    @Test
    fun uncertaintyCircleWhollyOutsideFails() {
        assertEquals(
            LocationBoundaryDecision.OUTSIDE,
            LocationBoundaryPolicy.classify(150.0, 20.0, 100.0),
        )
    }

    @Test
    fun farEdgeExactlyOnBoundaryIsInside() {
        assertEquals(
            LocationBoundaryDecision.INSIDE,
            LocationBoundaryPolicy.classify(90.0, 10.0, 100.0),
        )
    }

    @Test
    fun nearestEdgeExactlyOnBoundaryIsInconclusive() {
        assertEquals(
            LocationBoundaryDecision.INCONCLUSIVE,
            LocationBoundaryPolicy.classify(110.0, 10.0, 100.0),
        )
    }

    @Test
    fun nearestEdgePastBoundaryIsOutside() {
        assertEquals(
            LocationBoundaryDecision.OUTSIDE,
            LocationBoundaryPolicy.classify(111.0, 10.0, 100.0),
        )
    }
}
