package com.siteproof.app.verification

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.siteproof.app.verification.model.ChallengeIssue
import com.siteproof.app.verification.sensors.ChallengeGuidanceStatus
import com.siteproof.app.verification.sensors.ChallengeMovementGuidance
import kotlin.math.abs

private val GoodGuide = Color(0xFF2E7D32)
private val WrongGuide = Color(0xFFC62828)
private val FarGuide = Color(0xFFB26A00)
private val HandSkin = Color(0xFFD8A27C)
private val HandSkinDark = Color(0xFFB77B57)

@Composable
internal fun ChallengeMovementGuide(
    challenge: ChallengeIssue,
    guidance: ChallengeMovementGuidance,
) {
    val transition = rememberInfiniteTransition(label = "challenge-guide")
    val demo by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1200),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "phone-motion-demo",
    )

    val targetDegrees = challenge.parameters.targetDegrees.coerceAtLeast(1.0)
    val liveDegrees = abs(guidance.signedDegrees)
    val measuredFraction = (guidance.signedDegrees / targetDegrees).coerceIn(-1.15, 1.15).toFloat()
    val poseFraction = if (guidance.status == ChallengeGuidanceStatus.WAITING) demo else measuredFraction
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
            "You do not estimate the angle — SiteProof measures it live.",
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        HandHeldPhoneGuide(
            challengeType = challenge.type,
            targetDegrees = targetDegrees.toFloat(),
            poseFraction = poseFraction,
            guideColor = guideColor,
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("TARGET", style = MaterialTheme.typography.labelSmall)
                Text(
                    "${targetDegrees.toInt()}°",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                )
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("MEASURED", style = MaterialTheme.typography.labelSmall)
                Text(
                    measuredDegreesLabel(guidance),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = guideColor,
                )
            }
        }

        Text(
            challengeSecondaryHint(challenge.type),
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
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
private fun HandHeldPhoneGuide(
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
    val liveRotationY = expectedRotationY * poseFraction
    val liveRotationX = expectedRotationX * poseFraction

    Box(
        modifier = Modifier.size(width = 270.dp, height = 225.dp),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(width = 270.dp, height = 225.dp)) {
            val cx = size.width / 2f
            val handTop = size.height * 0.43f

            // Forearm.
            drawRoundRect(
                color = HandSkinDark,
                topLeft = Offset(cx - size.width * 0.15f, size.height * 0.70f),
                size = Size(size.width * 0.30f, size.height * 0.31f),
                cornerRadius = CornerRadius(size.width * 0.08f, size.width * 0.08f),
            )
            // Palm behind the phone.
            drawRoundRect(
                color = HandSkin,
                topLeft = Offset(cx - size.width * 0.22f, handTop),
                size = Size(size.width * 0.44f, size.height * 0.40f),
                cornerRadius = CornerRadius(size.width * 0.10f, size.width * 0.10f),
            )
            // Fingers wrapping around the phone edges.
            repeat(3) { index ->
                drawRoundRect(
                    color = HandSkin,
                    topLeft = Offset(
                        cx + size.width * 0.11f,
                        handTop + size.height * (0.035f + index * 0.085f),
                    ),
                    size = Size(size.width * 0.18f, size.height * 0.055f),
                    cornerRadius = CornerRadius(size.height * 0.03f, size.height * 0.03f),
                )
            }
            // Thumb on the opposite side.
            drawRoundRect(
                color = HandSkin,
                topLeft = Offset(cx - size.width * 0.30f, handTop + size.height * 0.15f),
                size = Size(size.width * 0.19f, size.height * 0.075f),
                cornerRadius = CornerRadius(size.height * 0.04f, size.height * 0.04f),
            )
        }

        // Ghost target pose: this is where the measured phone should end up.
        PhoneModel(
            modifier = Modifier
                .alpha(0.22f)
                .graphicsLayer {
                    rotationY = expectedRotationY
                    rotationX = expectedRotationX
                    cameraDistance = 16f * density
                },
            borderColor = guideColor,
            label = "TARGET",
        )

        // Live/demo pose. Once movement starts this follows sensor-measured angle.
        PhoneModel(
            modifier = Modifier.graphicsLayer {
                rotationY = liveRotationY
                rotationX = liveRotationX
                cameraDistance = 16f * density
                shadowElevation = 12f
            },
            borderColor = guideColor,
            label = "SITE",
        )

        Text(
            movementCue(challengeType),
            modifier = Modifier.align(
                when (challengeType) {
                    "ROTATE_LEFT" -> Alignment.CenterStart
                    "ROTATE_RIGHT" -> Alignment.CenterEnd
                    "TILT_UP" -> Alignment.TopCenter
                    "TILT_DOWN" -> Alignment.BottomCenter
                    else -> Alignment.TopCenter
                }
            ),
            color = guideColor,
            fontSize = 34.sp,
            fontWeight = FontWeight.Black,
        )
    }
}

@Composable
private fun PhoneModel(
    modifier: Modifier,
    borderColor: Color,
    label: String,
) {
    Box(
        modifier = modifier
            .size(width = 92.dp, height = 154.dp)
            .clip(RoundedCornerShape(19.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .border(4.dp, borderColor, RoundedCornerShape(19.dp)),
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .size(8.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.onSurfaceVariant),
        )
        Text(
            "TOP",
            modifier = Modifier.align(Alignment.TopCenter),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold,
        )
        Text(
            label,
            modifier = Modifier.align(Alignment.Center),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = FontWeight.Bold,
        )
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
    "TILT_UP" -> "Move the TOP edge away from you"
    "TILT_DOWN" -> "Move the TOP edge toward you"
    "ROTATE_RIGHT" -> "Turn the whole phone to your RIGHT"
    "ROTATE_LEFT" -> "Turn the whole phone to your LEFT"
    else -> "Follow the movement shown"
}

private fun challengeSecondaryHint(type: String): String = when (type) {
    "TILT_UP" -> "Follow the hand-and-phone animation. Stop when the measured angle reaches the green target range."
    "TILT_DOWN" -> "Follow the hand-and-phone animation. Stop when the measured angle reaches the green target range."
    "ROTATE_RIGHT" -> "Keep the phone upright and point the camera right like turning your head. Do not twist the screen clockwise."
    "ROTATE_LEFT" -> "Keep the phone upright and point the camera left like turning your head. Do not twist the screen counter-clockwise."
    else -> "Keep the inspection site visible while moving."
}

private fun movementCue(type: String): String = when (type) {
    "ROTATE_RIGHT" -> "→"
    "ROTATE_LEFT" -> "←"
    "TILT_UP" -> "↑"
    "TILT_DOWN" -> "↓"
    else -> "◆"
}

private fun measuredDegreesLabel(guidance: ChallengeMovementGuidance): String {
    val degrees = abs(guidance.signedDegrees).coerceAtMost(999.0)
    val suffix = if (guidance.status == ChallengeGuidanceStatus.WRONG_DIRECTION) " wrong way" else ""
    return "${degrees.toInt()}°$suffix"
}

private fun guidanceLabel(status: ChallengeGuidanceStatus): String = when (status) {
    ChallengeGuidanceStatus.WAITING -> "FOLLOW THE 3D DEMO"
    ChallengeGuidanceStatus.WRONG_DIRECTION -> "WRONG WAY — FOLLOW THE HAND"
    ChallengeGuidanceStatus.TOO_LITTLE -> "KEEP MOVING"
    ChallengeGuidanceStatus.GOOD_RANGE -> "GOOD — HOLD HERE"
    ChallengeGuidanceStatus.TOO_FAR -> "TOO FAR — MOVE BACK SLIGHTLY"
}
