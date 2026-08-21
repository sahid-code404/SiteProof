package com.siteproof.app.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
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
        Color(0xFFFF9A43),
        Color(0xFFFF6508),
        Color(0xFFED4F00),
    ),
)

private val SiteProofLightColors = lightColorScheme(
    primary = Color(0xFFF25800),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFE9D9),
    onPrimaryContainer = Color(0xFF6F2800),
    secondary = Color(0xFF525B68),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFEDF0F4),
    onSecondaryContainer = Color(0xFF303741),
    tertiary = Color(0xFF9A5A08),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFEFD7),
    onTertiaryContainer = Color(0xFF5B3700),
    background = Color(0xFFF3F5F8),
    onBackground = Color(0xFF17191D),
    surface = Color(0xFFFCFCFD),
    onSurface = Color(0xFF17191D),
    surfaceVariant = Color(0xFFF0F2F5),
    onSurfaceVariant = Color(0xFF646B76),
    outline = Color(0xFFD4D8DE),
    outlineVariant = Color(0xFFE4E7EB),
    error = Color(0xFFB42318),
    onError = Color.White,
    errorContainer = Color(0xFFFFE8E6),
    onErrorContainer = Color(0xFF6C100C),
)

private val SiteProofDarkColors = darkColorScheme(
    primary = Color(0xFFFF7B27),
    onPrimary = Color(0xFF321000),
    primaryContainer = Color(0xFF562000),
    onPrimaryContainer = Color(0xFFFFD9BE),
    secondary = Color(0xFFB9C0CA),
    onSecondary = Color(0xFF252B33),
    secondaryContainer = Color(0xFF30353D),
    onSecondaryContainer = Color(0xFFE2E5E9),
    tertiary = Color(0xFFFFB75A),
    onTertiary = Color(0xFF402D00),
    tertiaryContainer = Color(0xFF5B4100),
    onTertiaryContainer = Color(0xFFFFDEA8),
    background = Color(0xFF08090B),
    onBackground = Color(0xFFF5F6F8),
    surface = Color(0xFF141519),
    onSurface = Color(0xFFF5F6F8),
    surfaceVariant = Color(0xFF202228),
    onSurfaceVariant = Color(0xFFA7ADB7),
    outline = Color(0xFF42464F),
    outlineVariant = Color(0xFF292C32),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
)

private val SiteProofShapes = Shapes(
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(26.dp),
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
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontSize = 15.sp, lineHeight = 22.sp),
    bodySmall = TextStyle(fontSize = 13.sp, lineHeight = 19.sp),
    labelLarge = TextStyle(
        fontSize = 14.sp,
        lineHeight = 20.sp,
        fontWeight = FontWeight.SemiBold,
    ),
)

@Composable
fun SiteProofTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) SiteProofDarkColors else SiteProofLightColors,
        typography = SiteProofTypography,
        shapes = SiteProofShapes,
        content = content,
    )
}
