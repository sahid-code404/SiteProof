package com.siteproof.app

import com.siteproof.app.verification.challengeInstruction
import org.junit.Assert.assertEquals
import org.junit.Test

class ChallengeMovementGuideCopyTest {
    @Test
    fun rotateGuidanceUsesYawLanguage() {
        assertEquals("Turn the phone to your right", challengeInstruction("ROTATE_RIGHT"))
        assertEquals("Turn the phone to your left", challengeInstruction("ROTATE_LEFT"))
    }

    @Test
    fun tiltGuidanceKeepsEstablishedPhysicalMeaning() {
        assertEquals("Tilt the TOP of the phone away from you", challengeInstruction("TILT_UP"))
        assertEquals("Tilt the TOP of the phone toward you", challengeInstruction("TILT_DOWN"))
    }
}
