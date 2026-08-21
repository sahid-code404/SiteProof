package com.siteproof.app.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import com.siteproof.app.BuildConfig
import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.io.File
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.CacheControl
import okhttp3.OkHttpClient
import okhttp3.Request

@JsonClass(generateAdapter = false)
data class AppUpdateInfo(
    val versionCode: Int,
    val versionName: String,
    val apkUrl: String,
    val sha256: String,
    val notes: String? = null,
)

enum class InstallLaunchResult {
    INSTALLER_OPENED,
    PERMISSION_REQUIRED,
}

class DevAppUpdateManager(private val context: Context) {
    private val client = OkHttpClient.Builder()
        .followRedirects(true)
        .followSslRedirects(true)
        .build()
    private val adapter = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()
        .adapter(AppUpdateInfo::class.java)

    suspend fun checkForUpdate(): AppUpdateInfo? = withContext(Dispatchers.IO) {
        val manifestUrl = cacheBusted(BuildConfig.SITEPROOF_UPDATE_MANIFEST_URL, System.currentTimeMillis())
        val request = Request.Builder()
            .url(manifestUrl)
            .cacheControl(CacheControl.FORCE_NETWORK)
            .get()
            .build()
        client.newCall(request).execute().use { response ->
            check(response.isSuccessful) {
                "Update check failed with HTTP ${response.code}."
            }
            val body = response.body?.string() ?: error("Update manifest was empty.")
            val info = adapter.fromJson(body) ?: error("Update manifest was invalid.")
            require(info.versionCode > 0) { "Update version code is invalid." }
            require(info.apkUrl.startsWith("https://")) { "Update APK must use HTTPS." }
            require(info.sha256.matches(Regex("[0-9a-fA-F]{64}"))) {
                "Update SHA-256 is invalid."
            }
            if (info.versionCode > BuildConfig.VERSION_CODE) info else null
        }
    }

    suspend fun download(update: AppUpdateInfo): File = withContext(Dispatchers.IO) {
        val directory = File(context.cacheDir, "updates").apply { mkdirs() }
        val destination = File(directory, "SiteProof-${update.versionCode}.apk")
        val request = Request.Builder()
            .url(cacheBusted(update.apkUrl, update.versionCode.toLong()))
            .cacheControl(CacheControl.FORCE_NETWORK)
            .get()
            .build()
        client.newCall(request).execute().use { response ->
            check(response.isSuccessful) {
                "Update download failed with HTTP ${response.code}."
            }
            val body = response.body ?: error("Update download was empty.")
            destination.outputStream().use { output -> body.byteStream().copyTo(output) }
        }
        val actual = sha256(destination)
        check(actual.equals(update.sha256, ignoreCase = true)) {
            destination.delete()
            "Downloaded update failed SHA-256 verification."
        }
        destination
    }

    fun launchInstaller(apk: File): InstallLaunchResult {
        require(apk.isFile && apk.length() > 0L) { "Downloaded update APK is missing." }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
            !context.packageManager.canRequestPackageInstalls()
        ) {
            val permissionIntent = Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${context.packageName}"),
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(permissionIntent)
            return InstallLaunchResult.PERMISSION_REQUIRED
        }

        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.updates",
            apk,
        )
        val installIntent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        context.startActivity(installIntent)
        return InstallLaunchResult.INSTALLER_OPENED
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun cacheBusted(url: String, value: Long): String {
        val separator = if (url.contains('?')) '&' else '?'
        return "$url${separator}siteproofVersion=$value"
    }
}
