package com.siteproof.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
fun LoginScreen(state: AuthState, onLogin: (String, String) -> Unit) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val loading = state is AuthState.Loading

    Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier.padding(horizontal = 28.dp, vertical = 42.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text("SITEPROOF", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            Text("Field assignments", style = MaterialTheme.typography.displaySmall)
            Text(
                "Sign in with your inspector account to view work assigned to you.",
                modifier = Modifier.padding(top = 8.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(32.dp))
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Email") },
                enabled = !loading,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("Password") },
                visualTransformation = PasswordVisualTransformation(),
                enabled = !loading,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            if (state is AuthState.Error) {
                Text(
                    state.message,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
            Spacer(Modifier.height(20.dp))
            Button(
                onClick = { onLogin(email, password) },
                enabled = !loading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(20.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                } else {
                    Text("SIGN IN")
                }
            }
            Spacer(Modifier.height(16.dp))
            Text(
                "Inspection data comes from the SiteProof backend. Gallery upload and verification capture are intentionally not part of Phase 2.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
