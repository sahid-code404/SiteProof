package com.siteproof.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.siteproof.app.ui.SiteProofApp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { SiteProofApp() }
        requestMicrophonePermissionIfNeeded()
    }

    private fun requestMicrophonePermissionIfNeeded() {
        if (
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.RECORD_AUDIO),
                REQUEST_MICROPHONE_PERMISSION,
            )
        }
    }

    private companion object {
        const val REQUEST_MICROPHONE_PERMISSION = 2001
    }
}
