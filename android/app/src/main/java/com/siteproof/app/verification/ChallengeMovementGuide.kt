package com.siteproof.app.verification

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.siteproof.app.verification.model.ChallengeIssue
import com.siteproof.app.verification.sensors.ChallengeGuidanceStatus
import com.siteproof.app.verification.sensors.ChallengeMovementGuidance

private val GoodGuide = Color(0xFF2E7D32)
private val WrongGuide = Color(0xFFC62828)
private val FarGuide = Color(0xFFB26A00)

@Composable
internal fun ChallengeMovementGuide(
    challenge: ChallengeIssue,
    guidance: ChallengeMovementGuidance,
) {
    val transition = rememberInfiniteTransition(label = "challenge-guide")
    val motion by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 900),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "phone-motion",
    )

    val rotationZ = when (challenge.type) {
        "ROTATE_RIGHT" -> motion * 22f
        "ROTATE_LEFT" -> motion * -22f
        else -> 0f
    }
    val rotationX = when (challenge.type) {
        "TILT_UP" -> motion * -32f
        "TILT_DOWN" -> motion * 32f
        else -> 0f
    }
    val arrow = when (challenge.type) {
        "ROTATE_RIGHT" -> "↻"
        "ROTATE_LEFT" -> "↺"
        "TILT_UP" -> "↗"
        "TILT_DOWN" -> "↙"
        else -> "◆"
    }
    val guideColor = guidanceColor(guidance.status)

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Text(
            challengeInstruction(challenge.type),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
        Text(
            challengeSecondaryHint(challenge.type),
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(width = 86.dp, height = 138.dp)
                    .graphicsLayer {
                        this.rotationZ = rotationZ
                        this.rotationX = rotationX
                    }
                    .clip(RoundedCornerShape(17.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .border(
                        width = 4.dp,
                        color = guideColor,
                        shape = RoundedCornerShape(17.dp),
                    ),
            ) {
                Text(
                    "TOP",
                    modifier = Modifier.align(Alignment.TopCenter),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                )
                Box(
                    modifier = Modifier
                        .align(Alignment.TopCenter)
                        .size(7.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.onSurfaceVariant),
                )
                Text(
                    "SITE",
                    modifier = Modifier.align(Alignment.Center),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                arrow,
                fontSize = 52.sp,
                modifier = Modifier.size(72.dp),
                color = guideColor,
                textAlign = TextAlign.Center,
            )
        }

        Text(
            "Move until the guide turns green",
            style = MaterialTheme.typography.labelLarge,
            textAlign = TextAlign.Center,
        )
        LinearProgressIndicator(
            progress = { guidance.progressFraction },
            modifier = Modifier.fillMaxWidth(),
            color = guideColor,
        )
        Text(
            guidanceLabel(guidance.status),
            color = guideColor,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(2.dp))
    }
}

@Composable
private fun guidanceColor(status: ChallengeGuidanceStatus): Color = when (status) {
    ChallengeGuidanceStatus.GOOD_RANGE -> GoodGuide
    ChallengeGuidanceStatus.WRONG_DIRECTION -> WrongGuide
    ChallengeGuidanceStatus.TOO_FAR -> FarGuide
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}

internal fun challengeInstruction(type: String): String = when (type) {
    "TILT_UP" -> "Tilt the TOP of the phone away from you"
    "TILT_DOWN" -> "Tilt the TOP of the phone toward you"
    "ROTATE_RIGHT" -> "Rotate the phone clockwise"
    "ROTATE_LEFT" -> "Rotate the phone counter-clockwise"
    else -> "Follow the movement shown"
}

private fun challengeSecondaryHint(type: String): String = when (type) {
    "TILT_UP" -> "Keep the screen facing you; push only the top edge away."
    "TILT_DOWN" -> "Keep the screen facing you; bring only the top edge toward you."
    "ROTATE_RIGHT" -> "Keep the screen facing you and turn it to the right."
    "ROTATE_LEFT" -> "Keep the screen facing you and turn it to the left."
    else -> "Keep the inspection site visible while moving."
}

private fun guidanceLabel(status: ChallengeGuidanceStatus): String = when (status) {
    ChallengeGuidanceStatus.WAITING -> "WAITING FOR MOVEMENT"
    ChallengeGuidanceStatus.WRONG_DIRECTION -> "WRONG DIRECTION"
    ChallengeGuidanceStatus.TOO_LITTLE -> "KEEP GOING"
    ChallengeGuidanceStatus.GOOD_RANGE -> "GOOD RANGE"
    ChallengeGuidanceStatus.TOO_FAR -> "TOO FAR — HOLD STEADY"
}
