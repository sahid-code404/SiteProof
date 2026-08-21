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
import androidx.compose.foundation.layout.fillMaxWidth
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.siteproof.app.verification.model.ChallengeIssue
import com.siteproof.app.verification.sensors.ChallengeGuidanceStatus
import com.siteproof.app.verification.sensors.ChallengeMovementGuidance
import kotlin.math.abs
import kotlin.math.roundToInt

private val GuideGood = Color(0xFF2F6B4D)
private val GuideWrong = Color(0xFFA9362E)
private val GuideFar = Color(0xFF986313)

@Composable
internal fun ChallengeMovementGuide(
    challenge: ChallengeIssue,
    guidance: ChallengeMovementGuidance,
) {
    val transition = rememberInfiniteTransition(label = "movement-guide")
    val demo by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1100),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "movement-demo",
    )

    val targetDegrees = challenge.parameters.targetDegrees.coerceAtLeast(1.0)
    val measured = abs(guidance.signedDegrees)
    val measuredFraction = (guidance.signedDegrees / targetDegrees).coerceIn(-1.15, 1.15).toFloat()
    val poseFraction = if (guidance.status == ChallengeGuidanceStatus.WAITING) demo else measuredFraction
    val guideColor = guidanceColor(guidance.status)
    val progress = guidance.progressFraction.coerceIn(0f, 1f)

    val accessibilitySummary = buildString {
        append(challengeInstruction(challenge.type))
        append(". Target ${targetDegrees.toInt()} degrees. ")
        append("Measured ${measured.toInt()} degrees. ")
        append("${guidanceLabel(guidance.status)}. ")
        append("Progress ${(progress * 100f).roundToInt()} percent.")
    }

    Column(
        modifier = Modifier.clearAndSetSemantics { contentDescription = accessibilitySummary },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            challengeInstruction(challenge.type),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
        )

        PhoneMotionGuide(
            challengeType = challenge.type,
            targetDegrees = targetDegrees.toFloat(),
            poseFraction = poseFraction,
            guideColor = guideColor,
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Metric("Target", "${targetDegrees.toInt()}°")
            Metric("Measured", measuredDegreesLabel(guidance), guideColor)
        }

        LinearProgressIndicator(
            progress = { progress },
            modifier = Modifier.fillMaxWidth(),
            color = guideColor,
        )

        Text(
            guidanceLabel(guidance.status),
            color = guideColor,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun Metric(label: String, value: String, valueColor: Color = MaterialTheme.colorScheme.onSurface) {
    Column {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleMedium, color = valueColor)
    }
}

@Composable
private fun PhoneMotionGuide(
    challengeType: String,
    targetDegrees: Float,
    poseFraction: Float,
    guideColor: Color,
) {
    val expectedRotationY = when (challengeType) {
        "ROTATE_RIGHT" -> targetDegrees
        "ROTATE_LEFT" -> -targetDegrees
        else -> 0f
    }
    val expectedRotationX = when (challengeType) {
        "TILT_UP" -> -targetDegrees
        "TILT_DOWN" -> targetDegrees
        else -> 0f
    }

    Box(
        modifier = Modifier.size(width = 220.dp, height = 170.dp),
        contentAlignment = Alignment.Center,
    ) {
        PhoneShape(
            modifier = Modifier
                .alpha(0.18f)
                .graphicsLayer {
                    rotationY = expectedRotationY
                    rotationX = expectedRotationX
                    cameraDistance = 16f * density
                },
            borderColor = guideColor,
        )

        PhoneShape(
            modifier = Modifier.graphicsLayer {
                rotationY = expectedRotationY * poseFraction
                rotationX = expectedRotationX * poseFraction
                cameraDistance = 16f * density
            },
            borderColor = guideColor,
        )

        Text(
            movementCue(challengeType),
            modifier = Modifier.align(cueAlignment(challengeType)),
            color = guideColor,
            fontSize = 32.sp,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun PhoneShape(modifier: Modifier, borderColor: Color) {
    Box(
        modifier = modifier
            .size(width = 86.dp, height = 142.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .border(3.dp, borderColor, RoundedCornerShape(18.dp)),
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .size(7.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.onSurfaceVariant),
        )
        Text(
            "TOP",
            modifier = Modifier.align(Alignment.TopCenter),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

private fun cueAlignment(type: String) = when (type) {
    "ROTATE_LEFT" -> Alignment.CenterStart
    "ROTATE_RIGHT" -> Alignment.CenterEnd
    "TILT_UP" -> Alignment.TopCenter
    "TILT_DOWN" -> Alignment.BottomCenter
    else -> Alignment.TopCenter
}

@Composable
private fun guidanceColor(status: ChallengeGuidanceStatus): Color = when (status) {
    ChallengeGuidanceStatus.GOOD_RANGE -> GuideGood
    ChallengeGuidanceStatus.WRONG_DIRECTION -> GuideWrong
    ChallengeGuidanceStatus.TOO_FAR -> GuideFar
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}

internal fun challengeInstruction(type: String): String = when (type) {
    "TILT_UP" -> "Move the TOP edge away from you"
    "TILT_DOWN" -> "Move the TOP edge toward you"
    "ROTATE_RIGHT" -> "Turn the whole phone to your RIGHT"
    "ROTATE_LEFT" -> "Turn the whole phone to your LEFT"
    else -> "Follow the movement shown"
}

private fun movementCue(type: String): String = when (type) {
    "ROTATE_RIGHT" -> "→"
    "ROTATE_LEFT" -> "←"
    "TILT_UP" -> "↑"
    "TILT_DOWN" -> "↓"
    else -> "•"
}

private fun measuredDegreesLabel(guidance: ChallengeMovementGuidance): String {
    val degrees = abs(guidance.signedDegrees).coerceAtMost(999.0)
    return if (guidance.status == ChallengeGuidanceStatus.WRONG_DIRECTION) {
        "${degrees.toInt()}° · wrong way"
    } else {
        "${degrees.toInt()}°"
    }
}

private fun guidanceLabel(status: ChallengeGuidanceStatus): String = when (status) {
    ChallengeGuidanceStatus.WAITING -> "Follow the arrow"
    ChallengeGuidanceStatus.WRONG_DIRECTION -> "Wrong direction"
    ChallengeGuidanceStatus.TOO_LITTLE -> "Keep moving"
    ChallengeGuidanceStatus.GOOD_RANGE -> "Hold here"
    ChallengeGuidanceStatus.TOO_FAR -> "Move back slightly"
}
