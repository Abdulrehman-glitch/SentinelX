package com.sentinelx.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

// "Sentinel Steel" palette, taken from the brand mark: graphite + brushed
// steel + signal red. Light is the primary identity; dark is user preference.
val SxCrimson = Color(0xFFC8102E)     // primary signal red (logo glow)
val SxCrimsonDark = Color(0xFF8F0B20)
val SxBlue = Color(0xFF1976D2)        // secondary blue
val SxBg = Color(0xFFF6F7FB)
val SxSurface = Color(0xFFFFFFFF)
val SxText = Color(0xFF171923)
val SxTextMuted = Color(0xFF626879)
val SxGreen = Color(0xFF168A60)       // healthy
val SxAmber = Color(0xFFA86600)       // warning
val SxRed = Color(0xFFD52D49)         // critical
val SxOffline = Color(0xFF8891A5)

// Dark-variant severity accents (higher luminance for dark surfaces).
val SxDarkCrimson = Color(0xFFFF4D5E)
val SxDarkBlue = Color(0xFF4CC9FF)
val SxDarkGreen = Color(0xFF42D69A)
val SxDarkAmber = Color(0xFFFFBE55)
val SxDarkRed = Color(0xFFFF5C73)

/** True when the active Sentinel Glass theme is the dark variant. */
val LocalSxDark = staticCompositionLocalOf { false }

private val LightColors = lightColorScheme(
    primary = SxCrimson,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFF8DDE1),
    onPrimaryContainer = SxCrimsonDark,
    secondary = SxBlue,
    onSecondary = Color.White,
    background = SxBg,
    onBackground = SxText,
    surface = SxSurface,
    onSurface = SxText,
    surfaceVariant = Color(0xFFEEF0F7),
    onSurfaceVariant = SxTextMuted,
    outline = Color(0xFFCBD0DE),
    error = SxRed,
)

private val DarkColors = darkColorScheme(
    primary = SxDarkCrimson,
    onPrimary = Color(0xFF4D0A14),
    primaryContainer = Color(0xFF5C0E1B),
    onPrimaryContainer = Color(0xFFFFD9DD),
    secondary = SxDarkBlue,
    background = Color(0xFF080A10),
    onBackground = Color(0xFFF5F6FA),
    surface = Color(0xFF10131C),
    onSurface = Color(0xFFF5F6FA),
    surfaceVariant = Color(0xFF1B1F2C),
    onSurfaceVariant = Color(0xFFA8AEBD),
    outline = Color(0xFF343B4E),
    error = SxDarkRed,
)

/** Severity accents resolved for the active variant. */
object SxTone {
    val healthy: Color @Composable get() = if (LocalSxDark.current) SxDarkGreen else SxGreen
    val warning: Color @Composable get() = if (LocalSxDark.current) SxDarkAmber else SxAmber
    val critical: Color @Composable get() = if (LocalSxDark.current) SxDarkRed else SxRed
    val offline: Color @Composable get() = SxOffline
    val accent: Color @Composable get() = if (LocalSxDark.current) SxDarkCrimson else SxCrimson
    val accentBlue: Color @Composable get() = if (LocalSxDark.current) SxDarkBlue else SxBlue
}

@Composable
fun SentinelXTheme(themeMode: String = "light", content: @Composable () -> Unit) {
    val dark = when (themeMode) {
        "dark" -> true
        "system" -> isSystemInDarkTheme()
        else -> false
    }
    CompositionLocalProvider(LocalSxDark provides dark) {
        MaterialTheme(
            colorScheme = if (dark) DarkColors else LightColors,
            content = content,
        )
    }
}
