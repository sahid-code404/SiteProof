package com.siteproof.app.verification.location

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.os.SystemClock
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import com.siteproof.app.verification.model.CaptureLocation
import com.siteproof.app.verification.model.CapturedLocationSample
import com.siteproof.app.verification.model.LocationReadiness
import com.siteproof.app.verification.model.LocationSummary
import com.siteproof.app.verification.util.VerificationMath
import java.io.File
import java.io.OutputStreamWriter
import java.time.Instant
import java.util.Locale
import java.util.zip.GZIPOutputStream
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine

class LocationRecorder(context: Context) {
    private val client: FusedLocationProviderClient = LocationServices.getFusedLocationProviderClient(context)
    private var captureStartNs: Long = 0L
    private val samples = mutableListOf<CapturedLocationSample>()
    private var callback: LocationCallback? = null

    @SuppressLint("MissingPermission")
    suspend fun freshLocation(
        expectedLatitude: Double,
        expectedLongitude: Double,
        allowedRadiusMeters: Int,
        maxAgeSeconds: Int = 10,
    ): LocationReadiness {
        val source = CancellationTokenSource()
        val location = suspendCancellableCoroutine<Location> { continuation ->
            client.getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, source.token)
                .addOnSuccessListener { value ->
                    if (value == null) continuation.resumeWithException(IllegalStateException("Unable to acquire a fresh GPS location."))
                    else continuation.resume(value)
                }
                .addOnFailureListener(continuation::resumeWithException)
            continuation.invokeOnCancellation { source.cancel() }
        }
        val ageSeconds = ((SystemClock.elapsedRealtimeNanos() - location.elapsedRealtimeNanos).coerceAtLeast(0L)) / 1_000_000_000.0
        if (ageSeconds > maxAgeSeconds) {
            throw IllegalStateException("Location is stale. Move to an open area and retry.")
        }
        val distance = VerificationMath.haversineMeters(
            expectedLatitude,
            expectedLongitude,
            location.latitude,
            location.longitude,
        )
        val accuracy = location.accuracy.toDouble().coerceAtLeast(0.0)
        return LocationReadiness(
            location = location.toCaptureLocation(),
            ageSeconds = ageSeconds,
            distanceMeters = distance,
            accuracyLabel = VerificationMath.accuracyLabel(accuracy),
            withinAllowedArea = distance <= allowedRadiusMeters,
            inconclusive = distance > allowedRadiusMeters && distance <= allowedRadiusMeters + accuracy,
        )
    }

    @SuppressLint("MissingPermission")
    fun startCapture(captureStartNs: Long) {
        stopCapture()
        this.captureStartNs = captureStartNs
        samples.clear()
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1_000L)
            .setMinUpdateIntervalMillis(1_000L)
            .build()
        val newCallback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                result.locations.forEach { location ->
                    val eventNs = location.elapsedRealtimeNanos
                    if (eventNs >= this@LocationRecorder.captureStartNs) {
                        samples += location.toSample(eventNs - this@LocationRecorder.captureStartNs)
                    }
                }
            }
        }
        callback = newCallback
        client.requestLocationUpdates(request, newCallback, null)
    }

    fun stopCapture(): List<CapturedLocationSample> {
        callback?.let(client::removeLocationUpdates)
        callback = null
        return samples.toList()
    }

    fun writePackage(file: File, captured: List<CapturedLocationSample>): LocationSummary {
        require(captured.isNotEmpty()) { "At least one location sample is required." }
        file.parentFile?.mkdirs()
        GZIPOutputStream(file.outputStream()).use { gzip ->
            OutputStreamWriter(gzip, Charsets.UTF_8).use { writer ->
                writer.write("[")
                captured.forEachIndexed { index, item ->
                    if (index > 0) writer.write(",")
                    writer.write(item.toJson())
                }
                writer.write("]")
            }
        }
        return LocationSummary(
            locationSamples = captured.size,
            bestAccuracyMeters = captured.minOf { it.accuracyMeters },
            firstRelativeTimestampNs = captured.first().relativeTimestampNs,
            lastRelativeTimestampNs = captured.last().relativeTimestampNs,
        )
    }

    private fun Location.toCaptureLocation(): CaptureLocation = CaptureLocation(
        latitude = latitude,
        longitude = longitude,
        accuracyMeters = accuracy.toDouble(),
        altitudeMeters = if (hasAltitude()) altitude else null,
        bearingDegrees = if (hasBearing()) bearing.toDouble() else null,
        speedMetersPerSecond = if (hasSpeed()) speed.toDouble() else null,
        capturedAt = Instant.ofEpochMilli(time).toString(),
        elapsedRealtimeNs = elapsedRealtimeNanos,
    )

    private fun Location.toSample(relativeNs: Long): CapturedLocationSample = CapturedLocationSample(
        relativeTimestampNs = relativeNs,
        latitude = latitude,
        longitude = longitude,
        accuracyMeters = accuracy.toDouble(),
        altitudeMeters = if (hasAltitude()) altitude else null,
        bearingDegrees = if (hasBearing()) bearing.toDouble() else null,
        speedMetersPerSecond = if (hasSpeed()) speed.toDouble() else null,
    )

    private fun CapturedLocationSample.toJson(): String {
        fun number(value: Double) = String.format(Locale.US, "%.8f", value)
        return buildString {
            append("{\"relativeTimestampNs\":$relativeTimestampNs")
            append(",\"latitude\":${number(latitude)}")
            append(",\"longitude\":${number(longitude)}")
            append(",\"accuracyMeters\":${number(accuracyMeters)}")
            altitudeMeters?.let { append(",\"altitudeMeters\":${number(it)}") }
            bearingDegrees?.let { append(",\"bearingDegrees\":${number(it)}") }
            speedMetersPerSecond?.let { append(",\"speedMetersPerSecond\":${number(it)}") }
            append("}")
        }
    }
}
