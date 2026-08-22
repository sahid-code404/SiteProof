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

val SiteProofOrangeGradient = Brush.linearGradient(listOf(Color(0xFFFF8A3D), Color(0xFFF45B0B), Color(0xFFDF4700)))

private val IndustrialLight = lightColorScheme(
    primary = Color(0xFFF45B0B),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFEDE3),
    onPrimaryContainer = Color(0xFF7B2C00),
    secondary = Color(0xFF59616B),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFEEF0F3),
    onSecondaryContainer = Color(0xFF30363D),
    tertiary = Color(0xFF986000),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFF1D3),
    onTertiaryContainer = Color(0xFF593700),
    background = Color(0xFFF4F5F7),
    onBackground = Color(0xFF17191D),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF17191D),
    surfaceVariant = Color(0xFFF0F2F5),
    onSurfaceVariant = Color(0xFF646B75),
    outline = Color(0xFFCBD0D7),
    outlineVariant = Color(0xFFE1E4E8),
    error = Color(0xFFB42318),
    onError = Color.White,
    errorContainer = Color(0xFFFFECEA),
    onErrorContainer = Color(0xFF6B110B),
)

private val IndustrialDark = darkColorScheme(
    primary = Color(0xFFFF7426),
    onPrimary = Color(0xFF2E1100),
    primaryContainer = Color(0xFF3A2115),
    onPrimaryContainer = Color(0xFFFFDCC6),
    secondary = Color(0xFFB8BFC8),
    onSecondary = Color(0xFF252A31),
    secondaryContainer = Color(0xFF242930),
    onSecondaryContainer = Color(0xFFE4E7EB),
    tertiary = Color(0xFFFFC463),
    onTertiary = Color(0xFF452B00),
    tertiaryContainer = Color(0xFF302713),
    onTertiaryContainer = Color(0xFFFFDFAB),
    background = Color(0xFF0B0D10),
    onBackground = Color(0xFFF2F4F6),
    surface = Color(0xFF15181D),
    onSurface = Color(0xFFF2F4F6),
    surfaceVariant = Color(0xFF22272E),
    onSurfaceVariant = Color(0xFFA5ACB5),
    outline = Color(0xFF404750),
    outlineVariant = Color(0xFF2A2F37),
    error = Color(0xFFFF9B93),
    onError = Color(0xFF3B0001),
    errorContainer = Color(0xFF351A1B),
    onErrorContainer = Color(0xFFFFDAD6),
)

private val IndustrialShapes = Shapes(
    extraSmall = RoundedCornerShape(10.dp),
    small = RoundedCornerShape(14.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(30.dp),
)

private val IndustrialTypography = Typography(
    headlineMedium = TextStyle(fontSize = 28.sp, lineHeight = 34.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.45f).sp),
    headlineSmall = TextStyle(fontSize = 24.sp, lineHeight = 30.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.3f).sp),
    titleLarge = TextStyle(fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.2f).sp),
    titleMedium = TextStyle(fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 21.sp),
    bodySmall = TextStyle(fontSize = 12.sp, lineHeight = 18.sp),
    labelLarge = TextStyle(fontSize = 14.sp, lineHeight = 18.sp, fontWeight = FontWeight.SemiBold),
    labelMedium = TextStyle(fontSize = 12.sp, lineHeight = 16.sp, fontWeight = FontWeight.SemiBold),
    labelSmall = TextStyle(fontSize = 10.sp, lineHeight = 14.sp, fontWeight = FontWeight.SemiBold),
)

@Composable
fun SiteProofTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) IndustrialDark else IndustrialLight,
        typography = IndustrialTypography,
        shapes = IndustrialShapes,
        content = content,
    )
}
