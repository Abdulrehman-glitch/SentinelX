package com.sentinelx.mobile.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.animateIntAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sentinelx.mobile.health.HealthStatus
import com.sentinelx.mobile.ui.theme.SxTone

@Composable
fun healthColor(status: HealthStatus): Color = when (status) {
    HealthStatus.HEALTHY -> SxTone.healthy
    HealthStatus.WARNING -> SxTone.warning
    HealthStatus.CRITICAL -> SxTone.critical
    HealthStatus.OFFLINE -> SxTone.offline
}

/**
 * Central animated health indicator: outer ring sweeps to the score, glow
 * follows the status colour, number counts between values.
 */
@Composable
fun HealthOrb(
    score: Int,
    status: HealthStatus,
    size: Dp = 190.dp,
    animate: Boolean = true,
    modifier: Modifier = Modifier,
) {
    val color = healthColor(status)
    val duration = if (animate) 600 else 0
    val animatedScore by animateIntAsState(score, tween(duration), label = "score")
    val sweep by animateFloatAsState(score / 100f * 300f, tween(duration), label = "sweep")
    val glow by animateColorAsState(color, tween(duration), label = "glow")
    val track = MaterialTheme.colorScheme.surfaceVariant
    val statusLabel = status.name

    Box(
        modifier
            .size(size)
            .semantics { contentDescription = "Health score $score out of 100, $statusLabel" },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(size)) {
            val stroke = 14.dp.toPx()
            val inset = stroke / 2 + 6.dp.toPx()
            val arcSize = Size(this.size.width - inset * 2, this.size.height - inset * 2)
            val topLeft = Offset(inset, inset)
            // Soft radial glow behind the ring.
            drawCircle(
                brush = Brush.radialGradient(listOf(glow.copy(alpha = 0.22f), Color.Transparent)),
                radius = this.size.minDimension / 2,
            )
            drawArc(
                color = track,
                startAngle = 120f,
                sweepAngle = 300f,
                useCenter = false,
                topLeft = topLeft,
                size = arcSize,
                style = Stroke(stroke, cap = StrokeCap.Round),
            )
            drawArc(
                color = glow,
                startAngle = 120f,
                sweepAngle = sweep,
                useCenter = false,
                topLeft = topLeft,
                size = arcSize,
                style = Stroke(stroke, cap = StrokeCap.Round),
            )
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                "$animatedScore",
                fontSize = 52.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Text(
                statusLabel,
                style = MaterialTheme.typography.labelLarge,
                color = glow,
                fontWeight = FontWeight.SemiBold,
                letterSpacing = 2.sp,
            )
        }
    }
}

/** Minimal line sparkline; values are clamped to [0, 100]. */
@Composable
fun Sparkline(
    values: List<Double>,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier.fillMaxWidth().height(24.dp)) {
        if (values.size < 2) return@Canvas
        val clamped = values.map { it.coerceIn(0.0, 100.0) }
        val stepX = size.width / (clamped.size - 1)
        val path = Path()
        clamped.forEachIndexed { i, v ->
            val x = i * stepX
            val y = size.height - (v / 100.0 * size.height).toFloat()
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, color, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round))
    }
}

/** Severity chip: colour + text label (never colour alone). */
@Composable
fun SeverityChip(severity: String) {
    val color = when (severity.lowercase()) {
        "critical" -> SxTone.critical
        "warning" -> SxTone.warning
        "info" -> SxTone.accentBlue
        else -> SxTone.offline
    }
    Box(
        Modifier
            .background(color.copy(alpha = 0.14f), RoundedCornerShape(8.dp))
            .padding(horizontal = 8.dp, vertical = 2.dp)
    ) {
        Text(
            severity.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = color,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
fun StatusDotLabel(color: Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(8.dp).background(color, RoundedCornerShape(50)))
        Spacer(Modifier.width(6.dp))
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun SectionLabel(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 4.dp),
    )
}

/** "12 seconds ago" style formatting for headers and event rows. */
fun relativeTime(epochMs: Long, nowMs: Long = System.currentTimeMillis()): String {
    if (epochMs <= 0) return "never"
    val delta = (nowMs - epochMs).coerceAtLeast(0)
    val seconds = delta / 1000
    return when {
        seconds < 5 -> "just now"
        seconds < 60 -> "${seconds}s ago"
        seconds < 3600 -> "${seconds / 60}m ago"
        seconds < 86_400 -> "${seconds / 3600}h ago"
        else -> "${seconds / 86_400}d ago"
    }
}
