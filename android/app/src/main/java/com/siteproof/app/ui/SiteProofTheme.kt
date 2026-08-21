package com.siteproof.app.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val SiteProofColors = lightColorScheme(
    primary = Color(0xFF2F6B4D),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE4EFE8),
    onPrimaryContainer = Color(0xFF173126),
    secondary = Color(0xFF56665D),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFEDF1EE),
    onSecondaryContainer = Color(0xFF24312B),
    tertiary = Color(0xFF986313),
    onTertiary = Color.White,
    background = Color(0xFFF5F6F3),
    onBackground = Color(0xFF18231E),
    surface = Color.White,
    onSurface = Color(0xFF18231E),
    surfaceVariant = Color(0xFFF0F3F0),
    onSurfaceVariant = Color(0xFF667169),
    outline = Color(0xFFD8DFDA),
    error = Color(0xFFA9362E),
    onError = Color.White,
)

private val SiteProofShapes = Shapes(
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(16.dp),
)

private val SiteProofTypography = Typography(
    headlineMedium = TextStyle(
        fontSize = 28.sp,
        lineHeight = 34.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = (-0.4f).sp,
    ),
    titleLarge = TextStyle(
        fontSize = 21.sp,
        lineHeight = 27.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    titleMedium = TextStyle(
        fontSize = 16.sp,
        lineHeight = 22.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    bodyLarge = TextStyle(
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyMedium = TextStyle(
        fontSize = 14.sp,
        lineHeight = 21.sp,
    ),
    bodySmall = TextStyle(
        fontSize = 12.sp,
        lineHeight = 18.sp,
    ),
    labelLarge = TextStyle(
        fontSize = 13.sp,
        lineHeight = 18.sp,
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
