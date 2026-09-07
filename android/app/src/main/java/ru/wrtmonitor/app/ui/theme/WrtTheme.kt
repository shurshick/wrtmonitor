package ru.wrtmonitor.app.ui.theme

import android.app.Activity
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColors = darkColorScheme(
    primary = Color(0xFF58D3ED),
    onPrimary = Color(0xFF003641),
    primaryContainer = Color(0xFF004E5D),
    onPrimaryContainer = Color(0xFF9EEBFA),
    secondary = Color(0xFF75DDA0),
    onSecondary = Color(0xFF05391F),
    secondaryContainer = Color(0xFF18512F),
    onSecondaryContainer = Color(0xFF99F6BC),
    tertiary = Color(0xFFFFCB6B),
    onTertiary = Color(0xFF432C00),
    tertiaryContainer = Color(0xFF604100),
    onTertiaryContainer = Color(0xFFFFDEA6),
    error = Color(0xFFFFB3B8),
    onError = Color(0xFF680018),
    errorContainer = Color(0xFF920026),
    onErrorContainer = Color(0xFFFFDADC),
    background = Color(0xFF090E14),
    onBackground = Color(0xFFE5EAF1),
    surface = Color(0xFF0F151D),
    onSurface = Color(0xFFE5EAF1),
    surfaceVariant = Color(0xFF19232F),
    onSurfaceVariant = Color(0xFFB9C7D5),
    surfaceContainerLowest = Color(0xFF070B10),
    surfaceContainerLow = Color(0xFF0D141C),
    surfaceContainer = Color(0xFF121A23),
    surfaceContainerHigh = Color(0xFF19232E),
    surfaceContainerHighest = Color(0xFF22303D),
    outline = Color(0xFF82929F),
    outlineVariant = Color(0xFF344552),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF00677B),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFA7EDFA),
    onPrimaryContainer = Color(0xFF004E5D),
    secondary = Color(0xFF25663E),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFA9F2C4),
    onSecondaryContainer = Color(0xFF0A4E2A),
    tertiary = Color(0xFF775A00),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFE08D),
    onTertiaryContainer = Color(0xFF5A4300),
    error = Color(0xFFBA1A2E),
    onError = Color.White,
    errorContainer = Color(0xFFFFDADC),
    onErrorContainer = Color(0xFF930025),
    background = Color(0xFFF5F7FA),
    onBackground = Color(0xFF172027),
    surface = Color(0xFFFAFCFF),
    onSurface = Color(0xFF172027),
    surfaceVariant = Color(0xFFE6EEF3),
    onSurfaceVariant = Color(0xFF43525D),
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color(0xFFF0F4F7),
    surfaceContainer = Color(0xFFEAF0F4),
    surfaceContainerHigh = Color(0xFFE3EBF0),
    surfaceContainerHighest = Color(0xFFDCE5EA),
    outline = Color(0xFF6F7F8A),
    outlineVariant = Color(0xFFBECBD3),
)

private val WrtTypography = Typography(
    displaySmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 36.sp, lineHeight = 42.sp),
    headlineLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 30.sp, lineHeight = 36.sp),
    headlineMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 26.sp, lineHeight = 32.sp),
    headlineSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 22.sp, lineHeight = 28.sp),
    titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 20.sp, lineHeight = 26.sp),
    titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp),
    titleSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 14.sp, lineHeight = 20.sp),
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, fontSize = 14.sp, lineHeight = 20.sp),
    bodySmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, fontSize = 12.sp, lineHeight = 17.sp),
    labelLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 14.sp, lineHeight = 20.sp),
    labelMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 12.sp, lineHeight = 16.sp),
    labelSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Medium, fontSize = 11.sp, lineHeight = 15.sp),
)

private val WrtShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp),
    small = RoundedCornerShape(6.dp),
    medium = RoundedCornerShape(8.dp),
    large = RoundedCornerShape(8.dp),
    extraLarge = RoundedCornerShape(8.dp),
)

@Composable
fun WrtMonitorTheme(darkTheme: Boolean, content: @Composable () -> Unit) {
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as? Activity)?.window ?: return@SideEffect
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = !darkTheme
                isAppearanceLightNavigationBars = !darkTheme
            }
        }
    }
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = WrtTypography,
        shapes = WrtShapes,
    ) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background,
            content = content,
        )
    }
}
