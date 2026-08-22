package com.siteproof.app.verification

import android.content.Context
import android.media.AudioAttributes
import android.os.Bundle
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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

private val GuideGood = Color(0xFF25834D)
private val GuideWrong = Color(0xFFC9372C)
private val GuideFar = Color(0xFFB05A00)
private val GuideOrange = Color(0xFFF56200)

/**
 * Process-lifetime TTS speaker for live verification guidance.
 *
 * ChallengeActive is intentionally short-lived: Compose removes that overlay while a movement
 * is checked and between challenge steps. Creating and shutting down TextToSpeech inside the
 * overlay can therefore cancel an utterance before it becomes audible. Keeping one engine on the
 * application context avoids that race and also avoids paying TTS initialization latency for
 * every challenge.
 */
private object ChallengeVoiceSpeaker {
    @Volatile
    private var engine: TextToSpeech? = null

    @Volatile
    private var initializing = false

    private var pendingPhrase: String? = null
    private var pendingUtteranceId: String? = null

    fun speak(context: Context, phrase: String, utteranceId: String) {
        if (phrase.isBlank()) return
        val ready = engine
        if (ready != null) {
            speakNow(ready, phrase, utteranceId)
            return
        }

        synchronized(this) {
            pendingPhrase = phrase
            pendingUtteranceId = utteranceId
            if (initializing || engine != null) {
                engine?.let { speakNow(it, phrase, utteranceId) }
                return
            }
            initializing = true

            val appContext = context.applicationContext
            var created: TextToSpeech? = null
            created = TextToSpeech(appContext) { status ->
                synchronized(this) {
                    initializing = false
                    val tts = created
                    if (status != TextToSpeech.SUCCESS || tts == null) {
                        tts?.shutdown()
                        pendingPhrase = null
                        pendingUtteranceId = null
                        return@TextToSpeech
                    }

                    val localeResult = tts.setLanguage(Locale.getDefault())
                    if (
                        localeResult == TextToSpeech.LANG_MISSING_DATA ||
                        localeResult == TextToSpeech.LANG_NOT_SUPPORTED
                    ) {
                        tts.setLanguage(Locale.US)
                    }
                    tts.setSpeechRate(0.92f)
                    tts.setPitch(1.0f)
                    tts.setAudioAttributes(
                        AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                            .build(),
                    )
                    engine = tts

                    val queuedPhrase = pendingPhrase
                    val queuedId = pendingUtteranceId
                    pendingPhrase = null
                    pendingUtteranceId = null
                    if (!queuedPhrase.isNullOrBlank() && queuedId != null) {
                        speakNow(tts, queuedPhrase, queuedId)
                    }
                }
            }
        }
    }

    private fun speakNow(tts: TextToSpeech, phrase: String, utteranceId: String) {
        val params = Bundle().apply {
            putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f)
        }
        tts.speak(phrase, TextToSpeech.QUEUE_FLUSH, params, utteranceId)
    }
}

@Composable
internal fun ChallengeMovementGuide(
    challenge: ChallengeIssue,
    guidance: ChallengeMovementGuidance,
) {
    val context = LocalContext.current
    LaunchedEffect(challenge.challengeId, guidance.status) {
        val phrase = if (guidance.status == ChallengeGuidanceStatus.WAITING) {
            movementVoiceInstruction(challenge.type)
        } else {
            movementVoiceStatus(guidance.status)
        }
        if (phrase.isNotBlank()) {
            ChallengeVoiceSpeaker.speak(
                context,
                phrase,
                "siteproof-${challenge.challengeId}-${guidance.status.name}",
            )
        }
    }

    val transition = rememberInfiniteTransition(label = "movement-guide")
    val demo by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 900),
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
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            challengeInstruction(challenge.type),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurface,
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
            trackColor = MaterialTheme.colorScheme.surfaceVariant,
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
private fun Metric(label: String, value: String, valueColor: Color = MaterialTheme.colorScheme.onSurface) {
    Column {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
        modifier = Modifier.size(width = 250.dp, height = 190.dp),
        contentAlignment = Alignment.Center,
    ) {
        PhoneShape(
            modifier = Modifier
                .alpha(0.16f)
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
                .background(GuideOrange.copy(alpha = 0.14f))
                .border(2.dp, GuideOrange.copy(alpha = 0.45f), CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                movementCue(challengeType),
                color = if (guideColor == MaterialTheme.colorScheme.onSurfaceVariant) GuideOrange else guideColor,
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
            .size(width = 88.dp, height = 146.dp)
            .clip(RoundedCornerShape(20.dp))
            .background(Color.White.copy(alpha = 0.94f))
            .border(3.dp, borderColor, RoundedCornerShape(20.dp)),
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

@Composable
private fun guidanceColor(status: ChallengeGuidanceStatus): Color = when (status) {
    ChallengeGuidanceStatus.GOOD_RANGE -> GuideGood
    ChallengeGuidanceStatus.WRONG_DIRECTION -> GuideWrong
    ChallengeGuidanceStatus.TOO_FAR -> GuideFar
    else -> GuideOrange
}

internal fun challengeInstruction(type: String): String = when (type) {
    "TILT_UP" -> "Move the TOP edge away from you"
    "TILT_DOWN" -> "Move the TOP edge toward you"
    "ROTATE_RIGHT" -> "Turn the whole phone to your RIGHT"
    "ROTATE_LEFT" -> "Turn the whole phone to your LEFT"
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
    ChallengeGuidanceStatus.TOO_LITTLE -> "Go further"
    ChallengeGuidanceStatus.GOOD_RANGE -> "Hold here"
    ChallengeGuidanceStatus.TOO_FAR -> "Move back slightly"
}
