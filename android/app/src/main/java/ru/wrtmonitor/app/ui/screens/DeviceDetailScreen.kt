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
import org.json.JSONObject
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
fun DeviceDetailScreen(
    serverUrl: String,
    accessToken: String,
    device: DeviceDto,
    onSessionExpired: () -> Unit,
    onOpenClients: () -> Unit,
    onOpenWifi: () -> Unit,
    onOpenNetwork: () -> Unit,
    onOpenSystem: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var state by remember(device.id) {
        mutableStateOf(DeviceDetailUiState(loading = true, device = device))
    }
    var historyRange by rememberSaveable(device.id) { mutableStateOf("live") }
    val historyRequestSerial = remember(device.id) { AtomicInteger(0) }

    suspend fun refreshTelemetry(showLoading: Boolean = true) {
        state = state.copy(loading = showLoading && state.telemetry == null, error = null)
        val result = withContext(Dispatchers.IO) {
            WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id)
        }
        if (result is ApiResult.Error && result.isUnauthorized()) {
            onSessionExpired()
            return
        }
        state = state.copy(
            loading = false,
            telemetry = (result as? ApiResult.Success)?.data ?: state.telemetry,
            error = (result as? ApiResult.Error)?.message,
        )
    }

    suspend fun refreshHistory(requestedRange: String, showLoading: Boolean = true) {
        val requestSerial = historyRequestSerial.incrementAndGet()
        state = state.copy(
            telemetryHistoryLoading = showLoading,
            telemetryHistoryError = null,
        )
        val result = withContext(Dispatchers.IO) {
            WrtMonitorApi(serverUrl, accessToken).getTelemetryHistory(device.id, 120, requestedRange)
        }
        if (requestSerial != historyRequestSerial.get()) return
        if (result is ApiResult.Error && result.isUnauthorized()) {
            onSessionExpired()
            return
        }
        state = state.copy(
            telemetryHistoryLoading = false,
            telemetryHistory = (result as? ApiResult.Success)?.data ?: state.telemetryHistory,
            loadedTelemetryRange = if (result is ApiResult.Success) requestedRange else state.loadedTelemetryRange,
            telemetryHistoryError = (result as? ApiResult.Error)?.message,
        )
    }

    LaunchedEffect(serverUrl, accessToken, device.id) {
        refreshTelemetry()
        while (true) {
            delay(5_000)
            refreshTelemetry(showLoading = false)
        }
    }

    LaunchedEffect(serverUrl, accessToken, device.id, historyRange) {
        refreshHistory(historyRange)
        while (historyRange == "live") {
            delay(5_000)
            refreshHistory(historyRange, showLoading = false)
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        RouterPageHeader(
            title = stringResource(R.string.nav_overview),
            subtitle = device.firmware.ifBlank { device.model },
            refreshing = state.loading,
            onRefresh = {
                scope.launch {
                    refreshTelemetry()
                    refreshHistory(historyRange)
                }
            },
        )
        when {
            state.loading -> Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            state.error != null && state.telemetry == null -> Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error)
            state.telemetry == null -> Text(stringResource(R.string.no_data))
            else -> RouterOverview(
                device,
                state.telemetry!!,
                state.telemetryHistory,
                historyRange,
                { historyRange = it },
                state.telemetryHistoryLoading,
                state.telemetryHistoryError,
                state.loadedTelemetryRange,
                onOpenClients,
                onOpenWifi,
                onOpenNetwork,
                onOpenSystem,
            )
        }
    }

}

@Composable
private fun RouterOverview(
    device: DeviceDto,
    telemetry: TelemetryDto,
    history: List<TelemetryHistoryPointDto>,
    historyRange: String,
    onHistoryRangeChange: (String) -> Unit,
    historyLoading: Boolean,
    historyError: String?,
    loadedHistoryRange: String?,
    onOpenClients: () -> Unit,
    onOpenWifi: () -> Unit,
    onOpenNetwork: () -> Unit,
    onOpenSystem: () -> Unit,
) {
    val payload = telemetry.payload
    val system = payload?.optJSONObject("system")
    val memory = system?.optJSONObject("memory")
    val network = telemetry.network ?: payload?.optJSONObject("network")
    val interfaces = network?.optJSONArray("interfaces") ?: network?.optJSONArray("interface")
    var wan: JSONObject? = null
    if (interfaces != null) {
        for (index in 0 until interfaces.length()) {
            interfaces.optJSONObject(index)?.takeIf { it.optString("interface") == "wan" }?.let { wan = it }
        }
    }
    val wanUp = wan?.optBoolean("up", false) == true
    val wanAddress = wan?.optJSONArray("ipv4")?.optString(0).orEmpty().ifBlank { stringResource(R.string.no_ip_address) }
    val clients = telemetry.clients ?: payload?.optJSONObject("clients")
    val clientCount = clients?.optInt("online_count", clients.optInt("count", 0)) ?: 0
    val wifi = telemetry.wifi ?: payload?.optJSONObject("wifi")
    val radios = wifi?.optJSONArray("radios")
    val firstRadio = radios?.optJSONObject(0)
    val firstWifi = firstRadio?.optJSONArray("interfaces")?.optJSONObject(0)
    val wifiLabel = firstWifi?.optString("ssid").orEmpty().ifBlank { stringResource(R.string.wifi_unavailable) }
    val uptime = system?.optLong("uptime", 0) ?: 0
    val availableMb = memory?.optLong("available_kb", 0)?.div(1024) ?: 0
    val totalMb = memory?.optLong("total_kb", 0)?.div(1024) ?: 0
    val memoryPercent = if (totalMb > 0) ((totalMb - availableMb).toDouble() / totalMb * 100).coerceIn(0.0, 100.0) else 0.0
    val load = system?.optString("load")?.toDoubleOrNull() ?: history.lastOrNull()?.load1m ?: 0.0

    val healthy = device.status == "online" && !telemetry.isStale
    SectionCard(
        title = if (healthy) stringResource(R.string.router_healthy) else stringResource(R.string.router_attention),
        subtitle = stringResource(R.string.last_contact_value, formatTimestamp(telemetry.createdAt) ?: stringResource(R.string.no_data)),
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(device.model, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            StatusPill(if (healthy) stringResource(R.string.online) else stringResource(R.string.offline), healthy)
        }
    }
    TrafficMonitorCard(
        history,
        historyRange,
        onHistoryRangeChange,
        historyLoading,
        historyError,
        loadedHistoryRange,
    )
    SectionCard(title = stringResource(R.string.live_resources)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            MetricTile(stringResource(R.string.uptime), formatDuration(uptime), Modifier.weight(1f))
            MetricTile(stringResource(R.string.load_1m), String.format("%.2f", load), Modifier.weight(1f), MaterialTheme.colorScheme.tertiary)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            MetricTile(stringResource(R.string.memory_used), "${memoryPercent.toInt()}%", Modifier.weight(1f), MaterialTheme.colorScheme.primary)
            MetricTile(stringResource(R.string.clients_online), clientCount.toString(), Modifier.weight(1f), MaterialTheme.colorScheme.secondary)
        }
    }
    SectionCard(title = stringResource(R.string.router_sections)) {
        DestinationRow(
            Icons.Default.Public,
            stringResource(R.string.internet),
            if (wanUp) stringResource(R.string.connected) else stringResource(R.string.disconnected),
            wanAddress,
            if (wanUp) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.error,
            onOpenNetwork,
        )
        DestinationRow(
            Icons.Default.People,
            stringResource(R.string.home_network),
            clientCount.toString(),
            stringResource(R.string.connected_devices),
            MaterialTheme.colorScheme.secondary,
            onOpenClients,
        )
        DestinationRow(
            Icons.Default.Wifi,
            stringResource(R.string.wifi),
            wifiLabel,
            stringResource(R.string.radio_count_value, radios?.length() ?: 0),
            MaterialTheme.colorScheme.primary,
            onOpenWifi,
        )
        DestinationRow(
            Icons.Default.Memory,
            stringResource(R.string.system),
            formatDuration(uptime),
            stringResource(R.string.system_resources_summary),
            MaterialTheme.colorScheme.tertiary,
            onOpenSystem,
        )
    }
}

@Composable
private fun TrafficMonitorCard(
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
                formatTrafficRate(latest?.rxBps ?: 0),
                Modifier.weight(1f),
                MaterialTheme.colorScheme.primary,
            )
            MetricTile(
                stringResource(R.string.transmit_rate),
                formatTrafficRate(latest?.txBps ?: 0),
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
private fun TelemetrySegmentedControl(
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

private data class TelemetryChartSeries(
    val label: String,
    val color: Color,
    val values: List<Double>,
)

@Composable
private fun TelemetryChart(
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
                points.map { it.load1m.coerceFinite() },
            ),
        )
        "memory" -> listOf(
            TelemetryChartSeries(
                stringResource(R.string.telemetry_metric_memory),
                secondary,
                points.map { it.memoryPercent.coerceFinite().coerceIn(0.0, 100.0) },
            ),
        )
        "clients" -> listOf(
            TelemetryChartSeries(
                stringResource(R.string.telemetry_metric_clients),
                primary,
                points.map { it.clientCount.coerceAtLeast(0).toDouble() },
            ),
        )
        else -> listOf(
            TelemetryChartSeries(
                stringResource(R.string.receive_rate),
                primary,
                points.map { it.rxBps.coerceAtLeast(0).toDouble() },
            ),
            TelemetryChartSeries(
                stringResource(R.string.transmit_rate),
                secondary,
                points.map { it.txBps.coerceAtLeast(0).toDouble() },
            ),
        )
    }
    val observedMaximum = series.maxOfOrNull { item -> item.values.maxOrNull() ?: 0.0 } ?: 0.0
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
                                "${item.label}: ${formatTelemetryAxisValue(item.values.lastOrNull() ?: 0.0, metric)}",
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
                            item.values.forEachIndexed { index, value ->
                                val x = size.width * index / (item.values.size - 1).toFloat()
                                val y = size.height - size.height * value.toFloat() / axisMaximum.toFloat()
                                if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
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

private fun Double.coerceFinite(): Double = if (isFinite()) this else 0.0

private fun formatTelemetryAxisValue(value: Double, metric: String, compact: Boolean = false): String = when (metric) {
    "traffic" -> if (compact) formatCompactTrafficRate(value) else formatTrafficRate(value.toLong())
    "memory" -> "${value.toInt()}%"
    "clients" -> value.toInt().toString()
    else -> String.format(Locale.getDefault(), "%.1f", value)
}

private fun formatCompactTrafficRate(value: Double): String = when {
    value >= 1_000_000_000 -> String.format(Locale.getDefault(), "%.1fG", value / 1_000_000_000.0)
    value >= 1_000_000 -> String.format(Locale.getDefault(), "%.1fM", value / 1_000_000.0)
    value >= 1_000 -> String.format(Locale.getDefault(), "%.0fk", value / 1_000.0)
    else -> value.toInt().toString()
}

private fun formatTelemetryAxisTime(value: String, range: String): String = runCatching {
    val timestamp = OffsetDateTime.parse(value).atZoneSameInstant(ZoneId.systemDefault())
    val pattern = if (range in setOf("live", "24h")) "HH:mm" else "dd MMM"
    timestamp.format(DateTimeFormatter.ofPattern(pattern, Locale.getDefault()))
}.getOrDefault("—")

private fun formatChartTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .atZoneSameInstant(ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("dd.MM HH:mm", Locale.getDefault()))
}.getOrDefault("—")

private fun formatTrafficRate(value: Long): String = when {
    value >= 1_000_000_000 -> String.format("%.2f Gbit/s", value / 1_000_000_000.0)
    value >= 1_000_000 -> String.format("%.2f Mbit/s", value / 1_000_000.0)
    value >= 1_000 -> String.format("%.1f kbit/s", value / 1_000.0)
    else -> "$value bit/s"
}

@Composable
internal fun AgentSection(
    agent: AgentStatusDto?,
    actionError: String,
    onCheckUpdate: () -> Unit,
    onSetInterval: (Int) -> Unit,
    onEnableAutoUpdate: () -> Unit,
    onDisableAutoUpdate: () -> Unit,
    onRollback: () -> Unit,
) {
    val capabilities = agent?.capabilities ?: emptyMap()
    val autoUpdateEnabled = agent?.autoUpdateEnabled == true
    var intervalInput by rememberSaveable(agent?.telemetryIntervalSeconds) {
        mutableStateOf(agent?.telemetryIntervalSeconds?.toString() ?: "60")
    }
    val intervalValue = intervalInput.toIntOrNull()
    val intervalError = intervalInput.isNotBlank() && (intervalValue == null || intervalValue < 5)
    SectionCard(
        title = stringResource(R.string.agent_section_title),
        subtitle = stringResource(R.string.agent_section_summary),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(agent?.version ?: stringResource(R.string.no_data), style = MaterialTheme.typography.titleMedium)
                Text(
                    stringResource(R.string.telemetry_interval_value, agent?.telemetryIntervalSeconds ?: 0),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            StatusPill(
                agent?.status ?: stringResource(R.string.no_data),
                agent?.status?.lowercase() in setOf("running", "online", "ok"),
            )
        }
        InfoRow(stringResource(R.string.available_version), agent?.availableVersion, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.last_update_check), formatTimestamp(agent?.lastUpdateCheck), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.update_status), agent?.lastUpdateStatus, stringResource(R.string.no_data))
        agent?.lastUpdateError?.takeIf(String::isNotBlank)?.let { MessageBanner(it, error = true) }
        if (capabilities.isEmpty()) MessageBanner(stringResource(R.string.capabilities_missing_reinstall))
    }
    if (capabilities["agent.update"] == true || capabilities["agent.set_interval"] == true || capabilities["agent.rollback"] == true) {
        ExpandableSettingsCard(
            title = stringResource(R.string.agent_management),
            summary = if (autoUpdateEnabled) stringResource(R.string.auto_update_enabled_summary) else stringResource(R.string.auto_update_disabled_summary),
        ) {
            if (capabilities["agent.update"] == true) {
                SwitchSettingRow(
                    title = stringResource(R.string.auto_update),
                    subtitle = if (autoUpdateEnabled) stringResource(R.string.enabled_value) else stringResource(R.string.disabled_value),
                    checked = autoUpdateEnabled,
                    onCheckedChange = { value -> if (value) onEnableAutoUpdate() else onDisableAutoUpdate() },
                )
                TonalActionButton(stringResource(R.string.check_update), onCheckUpdate, Modifier.align(Alignment.End))
            }
            if (capabilities["agent.set_interval"] == true) {
                OutlinedTextField(
                    value = intervalInput,
                    onValueChange = { value -> intervalInput = value.filter(Char::isDigit) },
                    label = { Text(stringResource(R.string.telemetry_interval_label)) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    isError = intervalError,
                    supportingText = { Text(stringResource(R.string.min_five_seconds)) },
                )
                PrimaryActionButton(
                    label = stringResource(R.string.change_interval),
                    onClick = { intervalValue?.let(onSetInterval) },
                    modifier = Modifier.align(Alignment.End),
                    enabled = intervalValue != null && intervalValue >= 5,
                )
            }
            if (capabilities["agent.rollback"] == true) {
                SecondaryActionButton(stringResource(R.string.rollback_action), onRollback, Modifier.align(Alignment.End))
            }
        }
    }
    if (capabilities.isNotEmpty()) {
        ExpandableSettingsCard(
            title = stringResource(R.string.capabilities),
            summary = capabilitiesSummary(capabilities),
        ) {
            groupedCapabilities(capabilities, agent?.capabilityReasons.orEmpty()).forEach { (title, values) ->
                InfoRow(title, values.joinToString(", "))
            }
        }
    }
    MessageBanner(actionError, error = true)
}

private fun formatTimestamp(value: String?): String? = runCatching {
    if (value.isNullOrBlank()) null else OffsetDateTime.parse(value)
        .atZoneSameInstant(ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm:ss"))
}.getOrNull()

@Composable
private fun formatDuration(seconds: Long): String {
    val days = seconds / 86_400
    val hours = (seconds % 86_400) / 3_600
    val minutes = (seconds % 3_600) / 60
    return listOfNotNull(
        days.takeIf { it > 0 }?.let { stringResource(R.string.duration_days_short, it.toInt()) },
        hours.takeIf { it > 0 }?.let { stringResource(R.string.duration_hours_short, it.toInt()) },
        stringResource(R.string.duration_minutes_short, minutes.toInt()),
    ).joinToString(" ")
}
