package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Public
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.AgentStatusDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.dto.TelemetryHistoryPointDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.ui.components.InfoRow
import ru.wrtmonitor.app.ui.components.DestinationRow
import ru.wrtmonitor.app.ui.components.ActionRow
import ru.wrtmonitor.app.ui.components.ExpandableSettingsCard
import ru.wrtmonitor.app.ui.components.MessageBanner
import ru.wrtmonitor.app.ui.components.MetricTile
import ru.wrtmonitor.app.ui.components.PrimaryActionButton
import ru.wrtmonitor.app.ui.components.RouterPageHeader
import ru.wrtmonitor.app.ui.components.SecondaryActionButton
import ru.wrtmonitor.app.ui.components.SectionCard
import ru.wrtmonitor.app.ui.components.StatusPill
import ru.wrtmonitor.app.ui.components.SwitchSettingRow
import ru.wrtmonitor.app.ui.components.TonalActionButton
import ru.wrtmonitor.app.viewmodel.DeviceDetailUiState
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.pow

@Composable
internal fun TrafficMonitorCard(
    points: List<TelemetryHistoryPointDto>,
    historyRange: String,
    onHistoryRangeChange: (String) -> Unit,
    loading: Boolean,
    error: String?,
    loadedRange: String?,
) {
    var chartMetric by rememberSaveable { mutableStateOf("traffic") }
    val latest = points.lastOrNull()
    val rangeOptions = listOf(
        "live" to stringResource(R.string.telemetry_range_live),
        "24h" to stringResource(R.string.telemetry_range_day),
        "7d" to stringResource(R.string.telemetry_range_week),
        "30d" to stringResource(R.string.telemetry_range_month),
    )
    val metricOptions = listOf(
        "traffic" to stringResource(R.string.telemetry_metric_traffic),
        "load" to stringResource(R.string.telemetry_metric_load),
        "memory" to stringResource(R.string.telemetry_metric_memory),
        "clients" to stringResource(R.string.telemetry_metric_clients),
    )
    val selectedRangeLabel = rangeOptions.first { it.first == historyRange }.second
    val loadedRangeLabel = rangeOptions.firstOrNull { it.first == loadedRange }?.second
    SectionCard(
        title = stringResource(R.string.telemetry_monitor),
        subtitle = if (historyRange == "live") {
            stringResource(R.string.live_update_interval)
        } else {
            stringResource(R.string.telemetry_selected_period, selectedRangeLabel)
        },
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            MetricTile(
                stringResource(R.string.receive_rate),
                latest?.rxBps?.let(::formatTrafficRate) ?: stringResource(R.string.no_data),
                Modifier.weight(1f),
                MaterialTheme.colorScheme.primary,
            )
            MetricTile(
                stringResource(R.string.transmit_rate),
                latest?.txBps?.let(::formatTrafficRate) ?: stringResource(R.string.no_data),
                Modifier.weight(1f),
                MaterialTheme.colorScheme.secondary,
            )
        }
        Text(
            stringResource(R.string.telemetry_period),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        TelemetrySegmentedControl(rangeOptions, historyRange, onHistoryRangeChange, columns = 4)
        if (loading) {
            Row(
                Modifier.fillMaxWidth().padding(vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                Text(
                    stringResource(R.string.telemetry_loading_period, selectedRangeLabel),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        error?.let { MessageBanner(stringResource(R.string.telemetry_load_failed, it), error = true) }
        if (!loading && loadedRangeLabel != null) {
            val first = points.firstOrNull()?.createdAt?.let(::formatChartTimestamp) ?: stringResource(R.string.no_data)
            val last = points.lastOrNull()?.createdAt?.let(::formatChartTimestamp) ?: stringResource(R.string.no_data)
            Text(
                stringResource(
                    R.string.telemetry_loaded_summary,
                    loadedRangeLabel,
                    points.size,
                    first,
                    last,
                ),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            stringResource(R.string.telemetry_graph_metric),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        TelemetrySegmentedControl(metricOptions, chartMetric, { chartMetric = it }, columns = 2)
        TelemetryChart(points, chartMetric, loadedRange ?: historyRange)
        Text(
            stringResource(R.string.telemetry_points, points.size),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.align(Alignment.End),
        )
    }
}
@Composable
internal fun TelemetrySegmentedControl(
    options: List<Pair<String, String>>,
    selected: String,
    onSelected: (String) -> Unit,
    columns: Int,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        options.chunked(columns).forEach { rowOptions ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                rowOptions.forEach { (value, label) ->
                    val active = selected == value
                    Surface(
                        onClick = { onSelected(value) },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(6.dp),
                        color = if (active) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.34f),
                        contentColor = if (active) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant,
                        border = BorderStroke(
                            1.dp,
                            if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,
                        ),
                    ) {
                        Text(
                            label,
                            modifier = Modifier.padding(horizontal = 4.dp, vertical = 8.dp),
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                            textAlign = TextAlign.Center,
                            maxLines = 1,
                        )
                    }
                }
                repeat(columns - rowOptions.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

internal data class TelemetryChartSeries(
    val label: String,
    val color: Color,
    val values: List<Double>,
)

@Composable
internal fun TelemetryChart(
    points: List<TelemetryHistoryPointDto>,
    metric: String,
    range: String,
) {
    val primary = MaterialTheme.colorScheme.primary
    val secondary = MaterialTheme.colorScheme.secondary
    val grid = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f)
    val series = when (metric) {
        "load" -> listOf(
            TelemetryChartSeries(
                stringResource(R.string.telemetry_metric_load),
                MaterialTheme.colorScheme.tertiary,
                points.map { it.load1m ?: Double.NaN },
            ),
        )
        "memory" -> listOf(
            TelemetryChartSeries(
                stringResource(R.string.telemetry_metric_memory),
                secondary,
                points.map { it.memoryPercent?.coerceIn(0.0, 100.0) ?: Double.NaN },
            ),
        )
        "clients" -> listOf(
            TelemetryChartSeries(
                stringResource(R.string.telemetry_metric_clients),
                primary,
                points.map { it.clientCount?.coerceAtLeast(0)?.toDouble() ?: Double.NaN },
            ),
        )
        else -> listOf(
            TelemetryChartSeries(
                stringResource(R.string.receive_rate),
                primary,
                points.map { it.rxBps?.coerceAtLeast(0)?.toDouble() ?: Double.NaN },
            ),
            TelemetryChartSeries(
                stringResource(R.string.transmit_rate),
                secondary,
                points.map { it.txBps?.coerceAtLeast(0)?.toDouble() ?: Double.NaN },
            ),
        )
    }
    val observedMaximum = series.flatMap { it.values }.filter(Double::isFinite).maxOrNull() ?: 0.0
    val axisMaximum = if (metric == "memory") 100.0 else niceTelemetryAxisMaximum(observedMaximum)
    val axisTicks = (3 downTo 0).map { axisMaximum * it / 3.0 }
    Box(
        Modifier
            .fillMaxWidth()
            .height(238.dp)
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.36f), RoundedCornerShape(6.dp)),
        contentAlignment = Alignment.Center,
    ) {
        if (points.size < 2) {
            Text(stringResource(R.string.collecting_data), color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            Column(Modifier.fillMaxWidth().padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    series.forEach { item ->
                        Row(horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(8.dp).background(item.color, CircleShape))
                            Text(
                                "${item.label}: ${item.values.lastOrNull()?.takeIf(Double::isFinite)?.let { formatTelemetryAxisValue(it, metric) } ?: stringResource(R.string.no_data)}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                Row(Modifier.fillMaxWidth().weight(1f)) {
                    Column(
                        Modifier.width(56.dp).fillMaxHeight().padding(end = 6.dp),
                        verticalArrangement = Arrangement.SpaceBetween,
                        horizontalAlignment = Alignment.End,
                    ) {
                        axisTicks.forEach { value ->
                            Text(
                                formatTelemetryAxisValue(value, metric, compact = true),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                            )
                        }
                    }
                    Canvas(Modifier.fillMaxHeight().weight(1f)) {
                        repeat(4) { row ->
                            val y = size.height * row / 3f
                            drawLine(grid, Offset(0f, y), Offset(size.width, y), strokeWidth = 1f)
                        }
                        repeat(3) { column ->
                            val x = size.width * column / 2f
                            drawLine(grid, Offset(x, 0f), Offset(x, size.height), strokeWidth = 1f)
                        }
                        series.forEach { item ->
                            val path = Path()
                            var drawing = false
                            item.values.forEachIndexed { index, value ->
                                if (!value.isFinite()) {
                                    drawing = false
                                    return@forEachIndexed
                                }
                                val x = size.width * index / (item.values.size - 1).toFloat()
                                val y = size.height - size.height * value.toFloat() / axisMaximum.toFloat()
                                if (!drawing) path.moveTo(x, y) else path.lineTo(x, y)
                                drawing = true
                            }
                            drawPath(path, item.color, style = Stroke(3f, cap = StrokeCap.Round))
                        }
                    }
                }
                val timePoints = listOf(points.first(), points[points.size / 2], points.last())
                Row(Modifier.fillMaxWidth().padding(start = 62.dp)) {
                    timePoints.forEachIndexed { index, point ->
                        Text(
                            formatTelemetryAxisTime(point.createdAt, range),
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = when (index) {
                                0 -> TextAlign.Start
                                2 -> TextAlign.End
                                else -> TextAlign.Center
                            },
                            maxLines = 1,
                        )
                    }
                }
            }
        }
    }
}

internal fun niceTelemetryAxisMaximum(value: Double): Double {
    if (!value.isFinite() || value <= 0.0) return 1.0
    val exponent = floor(log10(value))
    val magnitude = 10.0.pow(exponent)
    val fraction = value / magnitude
    val rounded = when {
        fraction <= 1.0 -> 1.0
        fraction <= 2.0 -> 2.0
        fraction <= 5.0 -> 5.0
        else -> 10.0
    }
    return rounded * magnitude
}

internal fun Double.coerceFinite(): Double = if (isFinite()) this else 0.0

internal fun formatTelemetryAxisValue(value: Double, metric: String, compact: Boolean = false): String = when (metric) {
    "traffic" -> if (compact) formatCompactTrafficRate(value) else formatTrafficRate(value.toLong())
    "memory" -> "${value.toInt()}%"
    "clients" -> value.toInt().toString()
    else -> String.format(Locale.getDefault(), "%.1f", value)
}

internal fun formatCompactTrafficRate(value: Double): String = when {
    value >= 1_000_000_000 -> String.format(Locale.getDefault(), "%.1fG", value / 1_000_000_000.0)
    value >= 1_000_000 -> String.format(Locale.getDefault(), "%.1fM", value / 1_000_000.0)
    value >= 1_000 -> String.format(Locale.getDefault(), "%.0fk", value / 1_000.0)
    else -> value.toInt().toString()
}

internal fun formatTelemetryAxisTime(value: String, range: String): String = runCatching {
    val timestamp = OffsetDateTime.parse(value).atZoneSameInstant(ZoneId.systemDefault())
    val pattern = if (range in setOf("live", "24h")) "HH:mm" else "dd MMM"
    timestamp.format(DateTimeFormatter.ofPattern(pattern, Locale.getDefault()))
}.getOrDefault("—")

internal fun formatChartTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .atZoneSameInstant(ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("dd.MM HH:mm", Locale.getDefault()))
}.getOrDefault("—")

internal fun formatTrafficRate(value: Long): String = when {
    value >= 1_000_000_000 -> String.format(Locale.getDefault(), "%.2f Gbit/s", value / 1_000_000_000.0)
    value >= 1_000_000 -> String.format(Locale.getDefault(), "%.2f Mbit/s", value / 1_000_000.0)
    value >= 1_000 -> String.format(Locale.getDefault(), "%.1f kbit/s", value / 1_000.0)
    else -> "$value bit/s"
}
