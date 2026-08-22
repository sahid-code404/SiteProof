package com.siteproof.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.siteproof.app.R

@Composable
fun LoginScreen(state: AuthState, onLogin: (String, String) -> Unit) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    var localError by remember { mutableStateOf<String?>(null) }
    val loading = state is AuthState.Loading
    val scheme = MaterialTheme.colorScheme

    Box(
        modifier = Modifier.fillMaxSize().background(scheme.background),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .size(240.dp)
                .align(Alignment.TopCenter)
                .padding(top = 10.dp)
                .blur(72.dp)
                .background(scheme.primary.copy(alpha = .24f), CircleShape),
        )

        Surface(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 24.dp).widthIn(max = 440.dp),
            shape = RoundedCornerShape(28.dp),
            color = scheme.surface,
            border = BorderStroke(1.dp, scheme.outlineVariant),
            shadowElevation = 8.dp,
        ) {
            Column(Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(15.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(11.dp)) {
                    Image(
                        painter = painterResource(R.drawable.ic_siteproof_launcher),
                        contentDescription = null,
                        modifier = Modifier.size(48.dp),
                    )
                    Column {
                        Text("SiteProof", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Text("Field verification", color = scheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                    }
                }

                Spacer(Modifier.height(3.dp))
                Text("Sign in", style = MaterialTheme.typography.headlineMedium)
                Text("Open your assignments and capture verifiable field evidence.", color = scheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)

                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it; localError = null },
                    label = { Text("Email") },
                    placeholder = { Text("name@example.com") },
                    enabled = !loading,
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(15.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = scheme.surface,
                        unfocusedContainerColor = scheme.surface,
                        focusedBorderColor = scheme.primary,
                        unfocusedBorderColor = scheme.outline,
                    ),
                )

                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it; localError = null },
                    label = { Text("Password") },
                    visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    trailingIcon = {
                        IconButton(onClick = { passwordVisible = !passwordVisible }, enabled = !loading) {
                            Icon(if (passwordVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility, contentDescription = if (passwordVisible) "Hide password" else "Show password")
                        }
                    },
                    enabled = !loading,
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(15.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = scheme.surface,
                        unfocusedContainerColor = scheme.surface,
                        focusedBorderColor = scheme.primary,
                        unfocusedBorderColor = scheme.outline,
                    ),
                )

                val errorMessage = localError ?: (state as? AuthState.Error)?.message
                if (errorMessage != null) {
                    Surface(shape = RoundedCornerShape(14.dp), color = scheme.errorContainer, border = BorderStroke(1.dp, scheme.error.copy(alpha = .25f))) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text("Sign-in failed", color = scheme.onErrorContainer, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                            Text(errorMessage, color = scheme.onErrorContainer, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }

                Button(
                    onClick = {
                        val normalized = email.trim()
                        when {
                            !Regex("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$").matches(normalized) -> localError = "Enter a valid email address."
                            password.length < 8 -> localError = "Password must contain at least 8 characters."
                            else -> onLogin(normalized, password)
                        }
                    },
                    enabled = !loading && email.isNotBlank() && password.isNotBlank(),
                    modifier = Modifier.fillMaxWidth().height(50.dp),
                    shape = RoundedCornerShape(15.dp),
                ) {
                    if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = scheme.onPrimary)
                    else Text("Sign in", style = MaterialTheme.typography.labelLarge)
                }

                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("Location", "Motion", "Evidence").forEach { label ->
                        Surface(Modifier.weight(1f), shape = RoundedCornerShape(11.dp), color = scheme.surfaceVariant, border = BorderStroke(1.dp, scheme.outlineVariant)) {
                            Box(Modifier.padding(vertical = 8.dp), contentAlignment = Alignment.Center) { Text(label, color = scheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall) }
                        }
                    }
                }
            }
        }
    }
}
