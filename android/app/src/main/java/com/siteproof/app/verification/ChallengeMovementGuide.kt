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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
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
    val transition = rememberInfiniteTransition(label = "human-hand-guide")
    val demoFraction by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1350),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "human-hand-motion",
    )

    val targetDegrees = challenge.parameters.targetDegrees.coerceAtLeast(1.0).toFloat()
    val liveFraction = (guidance.signedDegrees / targetDegrees).coerceIn(-1.15, 1.15).toFloat()
    val guideColor = guidanceColor(guidance.status)

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(9.dp),
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

        HumanHandMovementDiagram(
            challengeType = challenge.type,
            targetDegrees = targetDegrees,
            demoFraction = demoFraction,
            liveFraction = liveFraction,
            guideColor = guideColor,
        )

        Text(
            "SiteProof measures the movement for you — follow the hand, not a number.",
            style = MaterialTheme.typography.labelLarge,
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
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(2.dp))
    }
}

@Composable
private fun HumanHandMovementDiagram(
    challengeType: String,
    targetDegrees: Float,
    demoFraction: Float,
    liveFraction: Float,
    guideColor: Color,
) {
    val targetY = when (challengeType) {
        "ROTATE_RIGHT" -> targetDegrees
        "ROTATE_LEFT" -> -targetDegrees
        else -> 0f
    }
    val targetX = when (challengeType) {
        "TILT_UP" -> -targetDegrees
        "TILT_DOWN" -> targetDegrees
        else -> 0f
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        tonalElevation = 2.dp,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                "WATCH THE HAND",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold,
            )

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(154.dp),
                contentAlignment = Alignment.Center,
            ) {
                HumanHandPhonePose(
                    modifier = Modifier
                        .size(124.dp)
                        .alpha(0.20f)
                        .graphicsLayer {
                            rotationY = targetY
                            rotationX = targetX
                            cameraDistance = 18f * density
                        },
                    label = "TARGET",
                    outline = guideColor,
                )

                HumanHandPhonePose(
                    modifier = Modifier
                        .size(124.dp)
                        .graphicsLayer {
                            rotationY = targetY * demoFraction
                            rotationX = targetX * demoFraction
                            cameraDistance = 18f * density
                        },
                    label = "",
                    outline = Color.Transparent,
                )

                Text(
                    movementCue(challengeType),
                    modifier = Modifier.align(cueAlignment(challengeType)),
                    color = guideColor,
                    fontSize = 42.sp,
                    fontWeight = FontWeight.Black,
                )
            }

            Text(
                directionCaption(challengeType),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("START", style = MaterialTheme.typography.labelSmall)
                    HumanHandPhonePose(
                        modifier = Modifier.size(66.dp),
                        label = "",
                        outline = MaterialTheme.colorScheme.outlineVariant,
                    )
                }
                Column(
                    modifier = Modifier.weight(1f),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("YOU", style = MaterialTheme.typography.labelSmall)
                    HumanHandPhonePose(
                        modifier = Modifier
                            .size(66.dp)
                            .graphicsLayer {
                                rotationY = targetY * liveFraction
                                rotationX = targetX * liveFraction
                                cameraDistance = 18f * density
                            },
                        label = "",
                        outline = guideColor,
                    )
                }
                Column(
                    modifier = Modifier.weight(1f),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("TARGET", style = MaterialTheme.typography.labelSmall)
                    HumanHandPhonePose(
                        modifier = Modifier
                            .size(66.dp)
                            .graphicsLayer {
                                rotationY = targetY
                                rotationX = targetX
                                cameraDistance = 18f * density
                            },
                        label = "",
                        outline = GoodGuide,
                    )
                }
            }
        }
    }
}

@Composable
private fun HumanHandPhonePose(
    modifier: Modifier,
    label: String,
    outline: Color,
) {
    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center,
    ) {
        Text(
            "🤳",
            fontSize = 72.sp,
            textAlign = TextAlign.Center,
        )
        if (outline != Color.Transparent) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .border(2.dp, outline, RoundedCornerShape(18.dp)),
            )
        }
        if (label.isNotBlank()) {
            Text(
                label,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .background(
                        MaterialTheme.colorScheme.surface.copy(alpha = 0.88f),
                        RoundedCornerShape(8.dp),
                    )
                    .padding(horizontal = 6.dp, vertical = 2.dp),
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

private fun cueAlignment(type: String): Alignment = when (type) {
    "ROTATE_LEFT" -> Alignment.CenterStart
    "ROTATE_RIGHT" -> Alignment.CenterEnd
    "TILT_UP" -> Alignment.TopCenter
    "TILT_DOWN" -> Alignment.BottomCenter
    else -> Alignment.TopCenter
}

@Composable
private fun guidanceColor(status: ChallengeGuidanceStatus): Color = when (status) {
    ChallengeGuidanceStatus.GOOD_RANGE -> GoodGuide
    ChallengeGuidanceStatus.WRONG_DIRECTION -> WrongGuide
    ChallengeGuidanceStatus.TOO_FAR -> FarGuide
    else -> MaterialTheme.colorScheme.primary
}

internal fun challengeInstruction(type: String): String = when (type) {
    "TILT_UP" -> "Move the TOP edge away from you"
    "TILT_DOWN" -> "Move the TOP edge toward you"
    "ROTATE_RIGHT" -> "Turn the whole phone to your RIGHT"
    "ROTATE_LEFT" -> "Turn the whole phone to your LEFT"
    else -> "Follow the movement shown"
}

private fun challengeSecondaryHint(type: String): String = when (type) {
    "TILT_UP" -> "Keep holding the phone normally. Push only the TOP edge away from your face."
    "TILT_DOWN" -> "Keep holding the phone normally. Bring only the TOP edge toward your face."
    "ROTATE_RIGHT" -> "Keep the phone upright and point the camera to your RIGHT. Do not twist the screen clockwise."
    "ROTATE_LEFT" -> "Keep the phone upright and point the camera to your LEFT. Do not twist the screen counter-clockwise."
    else -> "Keep the inspection site visible while moving."
}

private fun movementCue(type: String): String = when (type) {
    "ROTATE_RIGHT" -> "→"
    "ROTATE_LEFT" -> "←"
    "TILT_UP" -> "TOP ↗"
    "TILT_DOWN" -> "TOP ↙"
    else -> "◆"
}

private fun directionCaption(type: String): String = when (type) {
    "ROTATE_RIGHT" -> "Sweep the camera RIGHT"
    "ROTATE_LEFT" -> "Sweep the camera LEFT"
    "TILT_UP" -> "TOP edge goes AWAY"
    "TILT_DOWN" -> "TOP edge comes TOWARD YOU"
    else -> "Copy the hand movement"
}

private fun guidanceLabel(status: ChallengeGuidanceStatus): String = when (status) {
    ChallengeGuidanceStatus.WAITING -> "COPY THE HAND MOVEMENT"
    ChallengeGuidanceStatus.WRONG_DIRECTION -> "WRONG WAY — MOVE THE OTHER WAY"
    ChallengeGuidanceStatus.TOO_LITTLE -> "KEEP MOVING TOWARD TARGET"
    ChallengeGuidanceStatus.GOOD_RANGE -> "GOOD — HOLD HERE"
    ChallengeGuidanceStatus.TOO_FAR -> "TOO FAR — MOVE BACK SLIGHTLY"
}
