package com.siteproof.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.siteproof.app.R
import com.siteproof.app.data.BackendEndpointSettings
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(state: AuthState, onLogin: (String, String) -> Unit) {
    val appContext = LocalContext.current.applicationContext
    val backendSettings = remember(appContext) { BackendEndpointSettings(appContext) }
    val scope = rememberCoroutineScope()
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    var serverSettingsOpen by remember { mutableStateOf(false) }
    var backendEndpoint by remember { mutableStateOf(backendSettings.configuredEndpoint().orEmpty()) }
    var backendStatus by remember { mutableStateOf<String?>(null) }
    var backendError by remember { mutableStateOf<String?>(null) }
    var backendCheckInProgress by remember { mutableStateOf(false) }
    val loading = state is AuthState.Loading

    Box(
        modifier = Modifier.fillMaxSize().background(SiteProofOrangeGradient),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier.size(190.dp).align(Alignment.TopEnd).padding(top = 18.dp, end = 12.dp).blur(42.dp).background(androidx.compose.ui.graphics.Color.White.copy(alpha = 0.18f), CircleShape),
        )
        Box(
            Modifier.size(160.dp).align(Alignment.BottomStart).padding(bottom = 20.dp).blur(46.dp).background(androidx.compose.ui.graphics.Color(0xFFFFC27A).copy(alpha = 0.28f), CircleShape),
        )
        Surface(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 28.dp).widthIn(max = 460.dp),
            shape = RoundedCornerShape(28.dp),
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.97f),
            border = BorderStroke(1.dp, androidx.compose.ui.graphics.Color.White.copy(alpha = 0.82f)),
            shadowElevation = 12.dp,
        ) {
            Column(
                modifier = Modifier.padding(horizontal = 24.dp, vertical = 28.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                Image(
                    painter = painterResource(R.drawable.ic_siteproof_launcher),
                    contentDescription = null,
                    modifier = Modifier.size(66.dp),
                )
                Spacer(Modifier.height(18.dp))
                Text("SiteProof", style = MaterialTheme.typography.headlineMedium)
                Text("Field Verification", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                Text(
                    "Sign in to view your assigned inspections.",
                    modifier = Modifier.padding(top = 6.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )

                Spacer(Modifier.height(24.dp))
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = { Text("Email") },
                    enabled = !loading && !backendCheckInProgress,
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                )
                Spacer(Modifier.height(14.dp))
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Password") },
                    visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    trailingIcon = {
                        IconButton(onClick = { passwordVisible = !passwordVisible }, enabled = !loading && !backendCheckInProgress) {
                            Icon(imageVector = if (passwordVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility, contentDescription = if (passwordVisible) "Hide password" else "Show password")
                        }
                    },
                    enabled = !loading && !backendCheckInProgress,
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                )

                TextButton(
                    onClick = {
                        serverSettingsOpen = !serverSettingsOpen
                        backendStatus = null
                        backendError = null
                    },
                    enabled = !loading && !backendCheckInProgress,
                    modifier = Modifier.align(Alignment.End),
                ) {
                    Text(if (serverSettingsOpen) "Hide server settings" else "Server settings")
                }

                if (serverSettingsOpen) {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                    ) {
                        Column(
                            modifier = Modifier.padding(14.dp),
                            verticalArrangement = Arrangement.spacedBy(9.dp),
                        ) {
                            Text("Backend connection", style = MaterialTheme.typography.titleSmall)
                            Text(
                                "Automatic discovery is used by default. If login returns HTTP 404, enter the backend IP or URL here and test it before signing in.",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                style = MaterialTheme.typography.bodySmall,
                            )
                            OutlinedTextField(
                                value = backendEndpoint,
                                onValueChange = {
                                    backendEndpoint = it
                                    backendStatus = null
                                    backendError = null
                                },
                                modifier = Modifier.fillMaxWidth(),
                                label = { Text("Backend IP or URL") },
                                placeholder = { Text("192.168.1.102:8000") },
                                singleLine = true,
                                enabled = !loading && !backendCheckInProgress,
                                shape = RoundedCornerShape(14.dp),
                            )
                            Button(
                                onClick = {
                                    backendCheckInProgress = true
                                    backendStatus = null
                                    backendError = null
                                    scope.launch {
                                        runCatching { backendSettings.configureAndValidate(backendEndpoint) }
                                            .onSuccess { normalized ->
                                                backendEndpoint = normalized
                                                backendStatus = "Connected to the current SiteProof backend. You can sign in now."
                                            }
                                            .onFailure { error ->
                                                backendError = error.message ?: "Could not validate the backend address."
                                            }
                                        backendCheckInProgress = false
                                    }
                                },
                                enabled = !loading && !backendCheckInProgress && backendEndpoint.isNotBlank(),
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(14.dp),
                            ) {
                                if (backendCheckInProgress) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(18.dp),
                                        strokeWidth = 2.dp,
                                        color = MaterialTheme.colorScheme.onPrimary,
                                    )
                                } else {
                                    Text("Test & save server")
                                }
                            }
                            TextButton(
                                onClick = {
                                    backendSettings.useAutomaticDiscovery()
                                    backendEndpoint = ""
                                    backendError = null
                                    backendStatus = "Automatic local discovery enabled."
                                },
                                enabled = !loading && !backendCheckInProgress,
                                modifier = Modifier.align(Alignment.CenterHorizontally),
                            ) {
                                Text("Use automatic discovery")
                            }
                            backendStatus?.let {
                                Text(it, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
                            }
                            backendError?.let {
                                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                    Spacer(Modifier.height(10.dp))
                }

                if (state is AuthState.Error) {
                    Text(state.message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 12.dp))
                }

                Spacer(Modifier.height(20.dp))
                Button(
                    onClick = { onLogin(email.trim(), password) },
                    enabled = !loading && !backendCheckInProgress && email.isNotBlank() && password.isNotBlank(),
                    modifier = Modifier.fillMaxWidth().height(54.dp),
                    shape = RoundedCornerShape(16.dp),
                ) {
                    if (loading) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                    } else {
                        Text("Sign in", style = MaterialTheme.typography.labelLarge)
                    }
                }
            }
        }
    }
}
