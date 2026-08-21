package com.siteproof.app

import com.siteproof.app.verification.challengeInstruction
import org.junit.Assert.assertEquals
import org.junit.Test

class ChallengeMovementGuideCopyTest {
    @Test
    fun rotateGuidanceUsesWholePhoneYawLanguage() {
        assertEquals("Turn the whole phone to your RIGHT", challengeInstruction("ROTATE_RIGHT"))
        assertEquals("Turn the whole phone to your LEFT", challengeInstruction("ROTATE_LEFT"))
    }

    @Test
    fun tiltGuidanceNamesTheTopEdgeMovement() {
        assertEquals("Move the TOP edge away from you", challengeInstruction("TILT_UP"))
        assertEquals("Move the TOP edge toward you", challengeInstruction("TILT_DOWN"))
    }
}
