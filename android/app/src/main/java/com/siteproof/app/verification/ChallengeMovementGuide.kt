package com.siteproof.app.verification

import android.speech.tts.TextToSpeech
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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.siteproof.app.verification.model.ChallengeIssue
import com.siteproof.app.verification.sensors.ChallengeGuidanceStatus
import com.siteproof.app.verification.sensors.ChallengeMovementGuidance
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

private val GuideGood = Color(0xFF54D78D)
private val GuideWrong = Color(0xFFFF7169)
private val GuideFar = Color(0xFFFFB357)
private val GuideOrange = Color(0xFFFF7B27)
private val GuideText = Color(0xFFF8F8FA)
private val GuideTextMuted = Color(0xFFBFC3CB)

@Composable
internal fun ChallengeMovementGuide(
    challenge: ChallengeIssue,
    guidance: ChallengeMovementGuidance,
) {
    val context = LocalContext.current
    var speech by remember { mutableStateOf<TextToSpeech?>(null) }
    DisposableEffect(context) {
        lateinit var engine: TextToSpeech
        engine = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                engine.language = Locale.getDefault()
                engine.setSpeechRate(0.92f)
                speech = engine
            }
        }
        onDispose {
            engine.stop()
            engine.shutdown()
            if (speech === engine) speech = null
        }
    }
    LaunchedEffect(challenge.challengeId, guidance.status, speech) {
        val engine = speech ?: return@LaunchedEffect
        val phrase = if (guidance.status == ChallengeGuidanceStatus.WAITING) {
            movementVoiceInstruction(challenge.type)
        } else {
            movementVoiceStatus(guidance.status)
        }
        if (phrase.isNotBlank()) {
            engine.speak(
                phrase,
                TextToSpeech.QUEUE_FLUSH,
                null,
                "siteproof-${challenge.challengeId}-${guidance.status.name}",
            )
        }
    }

    val transition = rememberInfiniteTransition(label = "movement-guide")
    val demo by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 920),
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
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            color = GuideText,
        )
        Text(
            "Keep the site visible while moving the phone",
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
            color = GuideTextMuted,
        )

        PhoneMotionGuide(
            challengeType = challenge.type,
            targetDegrees = targetDegrees.toFloat(),
            poseFraction = poseFraction,
            cuePhase = demo,
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
            trackColor = Color.White.copy(alpha = 0.15f),
        )

        Text(
            guidanceLabel(guidance.status),
            color = guideColor,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun Metric(label: String, value: String, valueColor: Color = GuideText) {
    Column {
        Text(label, style = MaterialTheme.typography.bodySmall, color = GuideTextMuted)
        Text(value, style = MaterialTheme.typography.titleMedium, color = valueColor, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun PhoneMotionGuide(
    challengeType: String,
    targetDegrees: Float,
    poseFraction: Float,
    cuePhase: Float,
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
    val arrowTravel = 15f * (cuePhase - 0.5f)

    Box(
        modifier = Modifier.size(width = 250.dp, height = 176.dp),
        contentAlignment = Alignment.Center,
    ) {
        PhoneShape(
            modifier = Modifier
                .alpha(0.17f)
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

        Box(
            modifier = Modifier
                .align(cueAlignment(challengeType))
                .size(68.dp)
                .graphicsLayer {
                    translationX = when (challengeType) {
                        "ROTATE_RIGHT" -> arrowTravel
                        "ROTATE_LEFT" -> -arrowTravel
                        else -> 0f
                    }
                    translationY = when (challengeType) {
                        "TILT_UP" -> -arrowTravel
                        "TILT_DOWN" -> arrowTravel
                        else -> 0f
                    }
                    scaleX = 0.96f + cuePhase * 0.08f
                    scaleY = scaleX
                }
                .clip(CircleShape)
                .background(GuideOrange.copy(alpha = 0.16f))
                .border(2.dp, GuideOrange.copy(alpha = 0.52f), CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                movementCue(challengeType),
                color = guideColor,
                fontSize = 52.sp,
                lineHeight = 54.sp,
                fontWeight = FontWeight.Black,
            )
        }
    }
}

@Composable
private fun PhoneShape(modifier: Modifier, borderColor: Color) {
    Box(
        modifier = modifier
            .size(width = 86.dp, height = 142.dp)
            .clip(RoundedCornerShape(21.dp))
            .background(Color(0xFF1A1B20).copy(alpha = 0.96f))
            .border(3.dp, borderColor, RoundedCornerShape(21.dp)),
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .size(7.dp)
                .clip(CircleShape)
                .background(GuideTextMuted),
        )
        Text(
            "TOP",
            modifier = Modifier.align(Alignment.TopCenter),
            style = MaterialTheme.typography.labelSmall,
            color = GuideTextMuted,
            fontWeight = FontWeight.Bold,
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

private fun guidanceColor(status: ChallengeGuidanceStatus): Color = when (status) {
    ChallengeGuidanceStatus.GOOD_RANGE -> GuideGood
    ChallengeGuidanceStatus.WRONG_DIRECTION -> GuideWrong
    ChallengeGuidanceStatus.TOO_FAR -> GuideFar
    else -> GuideOrange
}

internal fun challengeInstruction(type: String): String = when (type) {
    "TILT_UP" -> "Tilt the TOP away from you"
    "TILT_DOWN" -> "Tilt the TOP toward you"
    "ROTATE_RIGHT" -> "Rotate the phone RIGHT"
    "ROTATE_LEFT" -> "Rotate the phone LEFT"
    else -> "Follow the arrow"
}

internal fun movementVoiceInstruction(type: String): String = when (type) {
    "ROTATE_RIGHT" -> "Rotate right"
    "ROTATE_LEFT" -> "Rotate left"
    "TILT_UP" -> "Tilt up"
    "TILT_DOWN" -> "Tilt down"
    else -> "Follow the arrow"
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

internal fun movementVoiceStatus(status: ChallengeGuidanceStatus): String = when (status) {
    ChallengeGuidanceStatus.WAITING -> ""
    ChallengeGuidanceStatus.WRONG_DIRECTION -> "Wrong direction"
    ChallengeGuidanceStatus.TOO_LITTLE -> "Go further"
    ChallengeGuidanceStatus.GOOD_RANGE -> "Hold here"
    ChallengeGuidanceStatus.TOO_FAR -> "Move back slightly"
}

private fun guidanceLabel(status: ChallengeGuidanceStatus): String = when (status) {
    ChallengeGuidanceStatus.WAITING -> "Follow the arrow"
    ChallengeGuidanceStatus.WRONG_DIRECTION -> "Wrong direction"
    ChallengeGuidanceStatus.TOO_LITTLE -> "Go a little further"
    ChallengeGuidanceStatus.GOOD_RANGE -> "Hold here"
    ChallengeGuidanceStatus.TOO_FAR -> "Move back slightly"
}
