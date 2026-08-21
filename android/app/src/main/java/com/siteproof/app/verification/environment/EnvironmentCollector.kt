package com.siteproof.app.verification.environment

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.net.wifi.WifiManager
import androidx.core.content.ContextCompat
import java.nio.charset.StandardCharsets
import java.security.MessageDigest

/**
 * Captures a privacy-preserving Wi-Fi environment snapshot.
 *
 * SSIDs and raw BSSIDs are never persisted. Access-point identifiers are scoped to the
 * verification session, which keeps start/end observations comparable without enabling
 * cross-session tracking of nearby networks.
 */
class EnvironmentCollector(private val context: Context) {
    @SuppressLint("MissingPermission")
    fun snapshot(sessionId: String): EnvironmentSnapshot {
        val permissionGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        if (wifi == null) {
            return EnvironmentSnapshot(
                capturedAtEpochMs = System.currentTimeMillis(),
                wifiEnabled = false,
                permissionGranted = permissionGranted,
                accessPoints = emptyList(),
            )
        }

        val accessPoints = if (permissionGranted) {
            runCatching {
                wifi.scanResults
                    .asSequence()
                    .filter { result -> result.BSSID.isNotBlank() }
                    .sortedByDescending { result -> result.level }
                    .map { result ->
                        EnvironmentAccessPoint(
                            apHash = sessionScopedHash(sessionId, result.BSSID),
                            rssiDbm = result.level,
                            frequencyMhz = result.frequency,
                        )
                    }
                    .distinctBy { item -> item.apHash }
                    .take(MAX_ACCESS_POINTS)
                    .toList()
            }.getOrDefault(emptyList())
        } else {
            emptyList()
        }

        return EnvironmentSnapshot(
            capturedAtEpochMs = System.currentTimeMillis(),
            wifiEnabled = wifi.isWifiEnabled,
            permissionGranted = permissionGranted,
            accessPoints = accessPoints,
        )
    }

    private fun sessionScopedHash(sessionId: String, bssid: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val value = "siteproof-env-v1|$sessionId|${bssid.trim().lowercase()}"
        return digest.digest(value.toByteArray(StandardCharsets.UTF_8))
            .joinToString("") { byte -> "%02x".format(byte) }
    }

    companion object {
        private const val MAX_ACCESS_POINTS = 12
    }
}

data class EnvironmentSnapshot(
    val capturedAtEpochMs: Long,
    val wifiEnabled: Boolean,
    val permissionGranted: Boolean,
    val accessPoints: List<EnvironmentAccessPoint>,
)

data class EnvironmentAccessPoint(
    val apHash: String,
    val rssiDbm: Int,
    val frequencyMhz: Int,
)
