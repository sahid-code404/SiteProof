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
        Color(0xFFFF9A24),
        Color(0xFFFF6900),
        Color(0xFFF04C00),
    ),
)

private val SiteProofColors = lightColorScheme(
    primary = Color(0xFFFF6200),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFE8D5),
    onPrimaryContainer = Color(0xFF8A3300),
    secondary = Color(0xFF53606F),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFF1F3F6),
    onSecondaryContainer = Color(0xFF2E3640),
    tertiary = Color(0xFFB86800),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFEED0),
    onTertiaryContainer = Color(0xFF734100),
    background = Color(0xFFF8F9FB),
    onBackground = Color(0xFF1A1D22),
    surface = Color.White,
    onSurface = Color(0xFF1A1D22),
    surfaceVariant = Color(0xFFF4F5F7),
    onSurfaceVariant = Color(0xFF69717C),
    outline = Color(0xFFD9DEE5),
    outlineVariant = Color(0xFFE9ECF0),
    error = Color(0xFFB8322A),
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
