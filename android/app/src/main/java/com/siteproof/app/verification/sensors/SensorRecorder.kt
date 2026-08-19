package com.siteproof.app.verification.sensors

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import com.siteproof.app.verification.model.DeviceCapabilities
import com.siteproof.app.verification.model.SensorCounts
import java.io.BufferedWriter
import java.io.File
import java.io.OutputStreamWriter
import java.util.Locale
import java.util.zip.GZIPOutputStream

class SensorRecorder(context: Context) : SensorEventListener {
    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val lock = Any()
    private var captureStartNs: Long = 0L
    private var writer: BufferedWriter? = null
    private var counts = SensorCounts()

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
        writer = BufferedWriter(OutputStreamWriter(GZIPOutputStream(outputFile.outputStream()), Charsets.UTF_8))
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
        val values = event.values.joinToString(",") { value ->
            String.format(Locale.US, "%.8f", value)
        }
        val line = "{\"type\":\"$typeName\",\"sensorTimestampNs\":${event.timestamp}," +
            "\"relativeTimestampNs\":$relativeNs,\"values\":[$values],\"accuracy\":${event.accuracy}}\n"
        synchronized(lock) {
            writer?.write(line)
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
