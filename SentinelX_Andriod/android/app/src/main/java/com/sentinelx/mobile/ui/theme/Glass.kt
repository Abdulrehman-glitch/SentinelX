package com.sentinelx.mobile.ui.theme

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

// Apple-style frosted glass: translucent panel over a soft tinted gradient.
// Real backdrop blur needs API 31+ / extra deps, so the look is achieved with
// translucency + hairline borders + a faint indigo drop shadow instead.

private val GlassShape = RoundedCornerShape(24.dp)

@Composable
fun glassBackgroundBrush(): Brush {
    return if (isSystemInDarkTheme()) {
        Brush.linearGradient(
            listOf(Color(0xFF0B1120), Color(0xFF141C33), Color(0xFF1A1F3C)),
        )
    } else {
        Brush.linearGradient(
            listOf(Color(0xFFF2F5FF), Color(0xFFE9EEFB), Color(0xFFE4E5F9)),
        )
    }
}

/** Full-screen gradient backdrop that glass panels float on. */
@Composable
fun GlassBackground(content: @Composable () -> Unit) {
    Box(
        Modifier
            .fillMaxSize()
            .background(glassBackgroundBrush()),
    ) {
        content()
    }
}

/** Frosted translucent card. Content supplies its own padding. */
@Composable
fun GlassPanel(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val dark = isSystemInDarkTheme()
    val fill = if (dark) Color(0xFF1E293B).copy(alpha = 0.55f) else Color.White.copy(alpha = 0.62f)
    val edge = if (dark) Color.White.copy(alpha = 0.08f) else Color.White.copy(alpha = 0.85f)

    Box(
        modifier
            .shadow(
                elevation = 18.dp,
                shape = GlassShape,
                ambientColor = SxIndigo.copy(alpha = 0.10f),
                spotColor = SxIndigo.copy(alpha = 0.16f),
            )
            .clip(GlassShape)
            .background(fill)
            .border(1.dp, edge, GlassShape),
    ) {
        content()
    }
}
