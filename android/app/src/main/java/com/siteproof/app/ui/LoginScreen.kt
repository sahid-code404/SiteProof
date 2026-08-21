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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Brush
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
    val loading = state is AuthState.Loading
    val scheme = MaterialTheme.colorScheme

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(scheme.background, scheme.surfaceVariant.copy(alpha = 0.78f), scheme.background),
                ),
            ),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier
                .size(240.dp)
                .align(Alignment.TopEnd)
                .padding(top = 12.dp)
                .blur(58.dp)
                .background(scheme.primary.copy(alpha = 0.24f), CircleShape),
        )
        Box(
            Modifier
                .size(190.dp)
                .align(Alignment.BottomStart)
                .padding(bottom = 10.dp)
                .blur(52.dp)
                .background(scheme.primary.copy(alpha = 0.12f), CircleShape),
        )
        Surface(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 28.dp).widthIn(max = 460.dp),
            shape = RoundedCornerShape(30.dp),
            color = scheme.surface.copy(alpha = 0.88f),
            border = BorderStroke(1.dp, scheme.outlineVariant),
            shadowElevation = 14.dp,
        ) {
            Column(
                modifier = Modifier.padding(horizontal = 24.dp, vertical = 28.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                Surface(
                    shape = RoundedCornerShape(22.dp),
                    color = scheme.primaryContainer.copy(alpha = 0.7f),
                    border = BorderStroke(1.dp, scheme.primary.copy(alpha = 0.14f)),
                ) {
                    Image(
                        painter = painterResource(R.drawable.ic_siteproof_launcher),
                        contentDescription = null,
                        modifier = Modifier.padding(9.dp).size(54.dp),
                    )
                }
                Spacer(Modifier.height(20.dp))
                Text("Welcome to SiteProof", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Text("Trusted field verification", style = MaterialTheme.typography.titleMedium, color = scheme.primary, fontWeight = FontWeight.SemiBold)
                Text(
                    "Sign in to view assignments and capture verifiable evidence.",
                    modifier = Modifier.padding(top = 7.dp),
                    color = scheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )

                Spacer(Modifier.height(24.dp))
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = { Text("Email") },
                    enabled = !loading,
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
                        IconButton(onClick = { passwordVisible = !passwordVisible }, enabled = !loading) {
                            Icon(
                                imageVector = if (passwordVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                contentDescription = if (passwordVisible) "Hide password" else "Show password",
                            )
                        }
                    },
                    enabled = !loading,
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                )

                if (state is AuthState.Error) {
                    Surface(
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                        shape = RoundedCornerShape(14.dp),
                        color = scheme.errorContainer,
                    ) {
                        Text(
                            state.message,
                            color = scheme.onErrorContainer,
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(12.dp),
                        )
                    }
                }

                Spacer(Modifier.height(20.dp))
                Button(
                    onClick = { onLogin(email.trim(), password) },
                    enabled = !loading && email.isNotBlank() && password.isNotBlank(),
                    modifier = Modifier.fillMaxWidth().height(54.dp),
                    shape = RoundedCornerShape(16.dp),
                ) {
                    if (loading) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp, color = scheme.onPrimary)
                    } else {
                        Text("Sign in securely", style = MaterialTheme.typography.labelLarge)
                    }
                }
            }
        }
    }
}
