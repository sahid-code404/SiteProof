package com.siteproof.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { SiteProofApp() }
    }
}

@Composable
fun SiteProofApp() {
    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier.padding(28.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.Start,
            ) {
                Text("SITEPROOF", style = MaterialTheme.typography.labelLarge)
                Text("Field verification", style = MaterialTheme.typography.headlineLarge)
                Text(
                    "Phase 1 application shell. Inspection assignments and live verification arrive in the next milestones.",
                    modifier = Modifier.padding(vertical = 18.dp),
                )
                Button(onClick = { }) {
                    Text("SIGN IN — PHASE 2")
                }
            }
        }
    }
}
