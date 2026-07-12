package com.sentinelx.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Mirrors the web console's light "Operations Console" palette (--sx-* tokens).
val SxIndigo = Color(0xFF4F46E5)
val SxIndigoDark = Color(0xFF4338CA)
val SxBg = Color(0xFFEEF1F7)
val SxSurface = Color(0xFFFFFFFF)
val SxText = Color(0xFF1E293B)
val SxTextMuted = Color(0xFF64748B)
val SxGreen = Color(0xFF16A34A)
val SxAmber = Color(0xFFD97706)
val SxRed = Color(0xFFDC2626)

private val LightColors = lightColorScheme(
    primary = SxIndigo,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE0E7FF),
    onPrimaryContainer = SxIndigoDark,
    secondary = SxTextMuted,
    background = SxBg,
    onBackground = SxText,
    surface = SxSurface,
    onSurface = SxText,
    surfaceVariant = Color(0xFFF1F5F9),
    onSurfaceVariant = SxTextMuted,
    error = SxRed,
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF818CF8),
    onPrimary = Color(0xFF1E1B4B),
    background = Color(0xFF0F172A),
    onBackground = Color(0xFFE2E8F0),
    surface = Color(0xFF1E293B),
    onSurface = Color(0xFFE2E8F0),
    surfaceVariant = Color(0xFF334155),
    onSurfaceVariant = Color(0xFF94A3B8),
)

@Composable
fun SentinelXTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}
