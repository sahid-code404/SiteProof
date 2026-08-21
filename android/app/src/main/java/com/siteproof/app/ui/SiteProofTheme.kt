package com.siteproof.app.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val SiteProofOrangeGradient = Brush.linearGradient(
    colors = listOf(
        Color(0xFFFF9720),
        Color(0xFFFF6B08),
        Color(0xFFF05200),
    ),
)

private val SiteProofColors = lightColorScheme(
    primary = Color(0xFFF45A00),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFF1E7),
    onPrimaryContainer = Color(0xFF823300),
    secondary = Color(0xFF475467),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFF0F2F5),
    onSecondaryContainer = Color(0xFF303743),
    tertiary = Color(0xFF9D5B08),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFF3DF),
    onTertiaryContainer = Color(0xFF694000),
    background = Color(0xFFF7F8FA),
    onBackground = Color(0xFF1A1C20),
    surface = Color.White,
    onSurface = Color(0xFF1A1C20),
    surfaceVariant = Color(0xFFF4F5F7),
    onSurfaceVariant = Color(0xFF667085),
    outline = Color(0xFFDCE0E5),
    outlineVariant = Color(0xFFE9EBEF),
    error = Color(0xFFB42318),
    onError = Color.White,
)

private val SiteProofShapes = Shapes(
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(24.dp),
)

private val SiteProofTypography = Typography(
    headlineMedium = TextStyle(
        fontSize = 28.sp,
        lineHeight = 34.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = (-0.35f).sp,
    ),
    titleLarge = TextStyle(
        fontSize = 21.sp,
        lineHeight = 28.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    titleMedium = TextStyle(
        fontSize = 17.sp,
        lineHeight = 23.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    bodyLarge = TextStyle(
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyMedium = TextStyle(
        fontSize = 15.sp,
        lineHeight = 22.sp,
    ),
    bodySmall = TextStyle(
        fontSize = 13.sp,
        lineHeight = 19.sp,
    ),
    labelLarge = TextStyle(
        fontSize = 14.sp,
        lineHeight = 20.sp,
        fontWeight = FontWeight.SemiBold,
    ),
)

@Composable
fun SiteProofTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = SiteProofColors,
        typography = SiteProofTypography,
        shapes = SiteProofShapes,
        content = content,
    )
}
