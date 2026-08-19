package com.siteproof.app

import com.siteproof.app.verification.evidence.EvidenceHasher
import com.siteproof.app.verification.upload.UploadRetryPolicy
import com.siteproof.app.verification.util.VerificationMath
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class Phase3EvidenceTest {
    @Test
    fun sha256ChangesWhenEvidenceChanges() {
        val file = File.createTempFile("siteproof", ".bin")
        try {
            file.writeBytes(byteArrayOf(1, 2, 3, 4))
            val first = EvidenceHasher.sha256(file)
            assertEquals(first, EvidenceHasher.sha256(file))
            file.writeBytes(byteArrayOf(1, 2, 3, 5))
            assertNotEquals(first, EvidenceHasher.sha256(file))
        } finally {
            file.delete()
        }
    }

    @Test
    fun relativeTimelineUsesMonotonicAnchor() {
        assertEquals(250L, VerificationMath.relativeTimestampNs(1250L, 1000L))
    }

    @Test(expected = IllegalArgumentException::class)
    fun relativeTimelineRejectsPreStartEvents() {
        VerificationMath.relativeTimestampNs(999L, 1000L)
    }

    @Test
    fun retryPolicyDoesNotLoopPermanentClientErrors() {
        assertTrue(UploadRetryPolicy.shouldRetry(null))
        assertTrue(UploadRetryPolicy.shouldRetry(503))
        assertTrue(UploadRetryPolicy.shouldRetry(429))
        assertFalse(UploadRetryPolicy.shouldRetry(400))
        assertFalse(UploadRetryPolicy.shouldRetry(403))
    }
}
