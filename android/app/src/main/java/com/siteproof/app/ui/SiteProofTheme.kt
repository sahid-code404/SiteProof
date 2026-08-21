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
        Color(0xFFFF9A2F),
        Color(0xFFFF6800),
        Color(0xFFE94B00),
    ),
)

private val SiteProofColors = lightColorScheme(
    primary = Color(0xFFF56200),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFE8D4),
    onPrimaryContainer = Color(0xFF6F2900),
    secondary = Color(0xFF8B4D2A),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFEEE2),
    onSecondaryContainer = Color(0xFF4D2A17),
    tertiary = Color(0xFFB05A00),
    onTertiary = Color.White,
    background = Color(0xFFFFF8F2),
    onBackground = Color(0xFF241B16),
    surface = Color.White,
    onSurface = Color(0xFF241B16),
    surfaceVariant = Color(0xFFFFF1E5),
    onSurfaceVariant = Color(0xFF6A5B52),
    outline = Color(0xFFD9C5B8),
    error = Color(0xFFB52D26),
    onError = Color.White,
)

private val SiteProofShapes = Shapes(
    small = RoundedCornerShape(9.dp),
    medium = RoundedCornerShape(13.dp),
    large = RoundedCornerShape(18.dp),
)

private val SiteProofTypography = Typography(
    headlineMedium = TextStyle(
        fontSize = 30.sp,
        lineHeight = 36.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = (-0.4f).sp,
    ),
    titleLarge = TextStyle(
        fontSize = 22.sp,
        lineHeight = 29.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    titleMedium = TextStyle(
        fontSize = 17.sp,
        lineHeight = 24.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    bodyLarge = TextStyle(
        fontSize = 17.sp,
        lineHeight = 25.sp,
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
