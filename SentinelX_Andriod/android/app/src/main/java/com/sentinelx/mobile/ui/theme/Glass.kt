package com.sentinelx.mobile.ui.theme

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

// Sentinel Glass: translucent panels over a soft two-glow backdrop (purple
// top-left, blue bottom-right). Real backdrop blur needs API 31+ and offscreen
// rendering, so the look is translucency + hairline border + tinted shadow.

private val GlassShape = RoundedCornerShape(24.dp)

/** Full-screen backdrop: base wash plus two large soft radial glows. */
@Composable
fun GlassBackground(content: @Composable () -> Unit) {
    val dark = LocalSxDark.current
    val base = if (dark) Color(0xFF080A10) else SxBg
    val purpleGlow = if (dark) SxDarkPurple.copy(alpha = 0.16f) else SxIndigo.copy(alpha = 0.10f)
    val blueGlow = if (dark) SxDarkBlue.copy(alpha = 0.10f) else SxBlue.copy(alpha = 0.07f)

    Box(Modifier.fillMaxSize().background(base)) {
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(purpleGlow, Color.Transparent),
                        center = Offset(180f, 120f),
                        radius = 1400f,
                    )
                )
        )
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(blueGlow, Color.Transparent),
                        center = Offset(1080f, 2200f),
                        radius = 1200f,
                    )
                )
        )
        content()
    }
}

/** Frosted translucent card. Content supplies its own padding. */
@Composable
fun GlassPanel(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val dark = LocalSxDark.current
    val fill = if (dark) Color.White.copy(alpha = 0.08f) else Color.White.copy(alpha = 0.66f)
    val edge = if (dark) Color.White.copy(alpha = 0.10f) else Color.White.copy(alpha = 0.90f)
    val tint = if (dark) SxDarkPurple else SxIndigo

    Box(
        modifier
            .shadow(
                elevation = 14.dp,
                shape = GlassShape,
                ambientColor = tint.copy(alpha = 0.08f),
                spotColor = tint.copy(alpha = 0.14f),
            )
            .clip(GlassShape)
            .background(fill)
            .border(1.dp, edge, GlassShape),
    ) {
        content()
    }
}
