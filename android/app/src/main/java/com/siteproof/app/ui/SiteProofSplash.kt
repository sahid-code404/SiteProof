package com.siteproof.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun SiteProofSplash() {
    val scheme = MaterialTheme.colorScheme
    Box(Modifier.fillMaxSize().background(scheme.background), contentAlignment = Alignment.Center) {
        Box(
            Modifier
                .size(230.dp)
                .align(Alignment.Center)
                .blur(76.dp)
                .background(scheme.primary.copy(alpha = .22f), CircleShape),
        )
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Surface(
                modifier = Modifier.size(78.dp),
                shape = RoundedCornerShape(24.dp),
                color = scheme.surface,
                shadowElevation = 10.dp,
            ) {
                Box(Modifier.background(SiteProofOrangeGradient), contentAlignment = Alignment.Center) {
                    Text("SP", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Bold, letterSpacing = (-.6f).sp)
                }
            }
            Spacer(Modifier.height(20.dp))
            Text("SiteProof", style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(3.dp))
            Text("Field verification", style = MaterialTheme.typography.bodyMedium, color = scheme.onSurfaceVariant)
        }
    }
}
