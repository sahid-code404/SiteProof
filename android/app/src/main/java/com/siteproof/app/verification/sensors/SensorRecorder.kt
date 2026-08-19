package com.siteproof.app.verification.sensors

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import com.siteproof.app.verification.model.ChallengeClientSensorSummary
import com.siteproof.app.verification.model.ChallengeSensorSample
import com.siteproof.app.verification.model.DeviceCapabilities
import com.siteproof.app.verification.model.SensorCounts
import java.io.BufferedWriter
import java.io.File
import java.io.OutputStreamWriter
import java.util.Locale
import java.util.zip.GZIPOutputStream
import kotlin.math.sqrt

class SensorRecorder(context: Context) : SensorEventListener {
    data class ChallengeSlice(
        val samples: List<ChallengeSensorSample>,
        val summary: ChallengeClientSensorSummary,
    )

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val lock = Any()
    private var captureStartNs: Long = 0L
    private var writer: BufferedWriter? = null
    private var counts = SensorCounts()
    private val challengeBuffer = ArrayDeque<ChallengeSensorSample>()

    fun capabilities(): DeviceCapabilities = DeviceCapabilities(
        accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER) != null,
        gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE) != null,
        rotationVector = sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR) != null,
        magnetometer = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD) != null,
    )

    fun start(captureStartNs: Long, outputFile: File) {
        stop()
        outputFile.parentFile?.mkdirs()
        this.captureStartNs = captureStartNs
        counts = SensorCounts()
        synchronized(lock) {
            challengeBuffer.clear()
            writer = BufferedWriter(
                OutputStreamWriter(GZIPOutputStream(outputFile.outputStream()), Charsets.UTF_8),
            )
        }
        register(Sensor.TYPE_ACCELEROMETER)
        register(Sensor.TYPE_GYROSCOPE)
        register(Sensor.TYPE_ROTATION_VECTOR)
        register(Sensor.TYPE_MAGNETIC_FIELD)
    }

    private fun register(type: Int) {
        val sensor = sensorManager.getDefaultSensor(type) ?: return
        // 20,000 microseconds targets about 50 Hz without demanding SENSOR_DELAY_FASTEST.
        sensorManager.registerListener(this, sensor, 20_000)
    }

    fun stop(): SensorCounts {
        sensorManager.unregisterListener(this)
        synchronized(lock) {
            writer?.flush()
            writer?.close()
            writer = null
        }
        return counts
    }

    fun relativeNowNs(monotonicNowNs: Long): Long = (monotonicNowNs - captureStartNs).coerceAtLeast(0L)

    fun challengeSlice(startRelativeNs: Long, endRelativeNs: Long): ChallengeSlice = synchronized(lock) {
        // SensorEvent callbacks from different sensor types are not guaranteed to arrive in
        // globally timestamp-sorted order on real devices. The Phase 4 backend deliberately
        // requires one monotonic common timeline, so normalize the merged slice by the hardware
        // sensor timestamp before it is submitted.
        val samples = challengeBuffer
            .filter {
                it.relativeTimestampNs in startRelativeNs..endRelativeNs &&
                    it.type in setOf("ACCELEROMETER", "GYROSCOPE", "ROTATION_VECTOR")
            }
            .sortedBy { it.relativeTimestampNs }
        ChallengeSlice(
            samples = samples,
            summary = ChallengeClientSensorSummary(
                gyroSamples = samples.count { it.type == "GYROSCOPE" },
                rotationVectorSamples = samples.count { it.type == "ROTATION_VECTOR" },
                accelerometerSamples = samples.count { it.type == "ACCELEROMETER" },
            ),
        )
    }

    fun movementDetected(startRelativeNs: Long, endRelativeNs: Long): Boolean = synchronized(lock) {
        challengeBuffer.asSequence()
            .filter {
                it.type == "GYROSCOPE" &&
                    it.relativeTimestampNs in startRelativeNs..endRelativeNs
            }
            .any { sample ->
                val x = sample.values.getOrElse(0) { 0.0 }
                val y = sample.values.getOrElse(1) { 0.0 }
                val z = sample.values.getOrElse(2) { 0.0 }
                sqrt(x * x + y * y + z * z) >= 0.18
            }
    }

    override fun onSensorChanged(event: SensorEvent) {
        if (event.timestamp < captureStartNs) return
        val typeName = when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> "ACCELEROMETER"
            Sensor.TYPE_GYROSCOPE -> "GYROSCOPE"
            Sensor.TYPE_ROTATION_VECTOR -> "ROTATION_VECTOR"
            Sensor.TYPE_MAGNETIC_FIELD -> "MAGNETOMETER"
            else -> return
        }
        val relativeNs = event.timestamp - captureStartNs
        val doubleValues = event.values.map { it.toDouble() }
        val values = event.values.joinToString(",") { value ->
            String.format(Locale.US, "%.8f", value)
        }
        val line = "{\"type\":\"$typeName\",\"sensorTimestampNs\":${event.timestamp}," +
            "\"relativeTimestampNs\":$relativeNs,\"values\":[$values],\"accuracy\":${event.accuracy}}\n"
        synchronized(lock) {
            writer?.write(line)
            if (typeName != "MAGNETOMETER") {
                challengeBuffer.addLast(
                    ChallengeSensorSample(
                        type = typeName,
                        relativeTimestampNs = relativeNs,
                        values = doubleValues,
                        accuracy = event.accuracy,
                    ),
                )
                // Capture is capped at 60 seconds. This is a second defensive memory bound.
                while (challengeBuffer.size > 15_000) challengeBuffer.removeFirst()
            }
            counts = when (event.sensor.type) {
                Sensor.TYPE_ACCELEROMETER -> counts.copy(accelerometer = counts.accelerometer + 1)
                Sensor.TYPE_GYROSCOPE -> counts.copy(gyroscope = counts.gyroscope + 1)
                Sensor.TYPE_ROTATION_VECTOR -> counts.copy(rotationVector = counts.rotationVector + 1)
                Sensor.TYPE_MAGNETIC_FIELD -> counts.copy(magnetometer = counts.magnetometer + 1)
                else -> counts
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
}
