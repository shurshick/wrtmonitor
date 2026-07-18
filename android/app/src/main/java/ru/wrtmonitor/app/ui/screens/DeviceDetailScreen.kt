package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
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
    fun refresh(showLoading: Boolean = true) {
        state = state.copy(loading = showLoading && state.telemetry == null, error = null)
        scope.launch {
            val (telemetryResult, historyResult) = withContext(Dispatchers.IO) {
                WrtMonitorApi(serverUrl, accessToken).let { api ->
                    api.getLatestTelemetry(device.id) to api.getTelemetryHistory(device.id, 120, historyRange)
                }
            }
            if (
                telemetryResult is ApiResult.Error && telemetryResult.isUnauthorized() ||
                historyResult is ApiResult.Error && historyResult.isUnauthorized()
            ) {
                onSessionExpired()
                return@launch
            }
            val telemetry = (telemetryResult as? ApiResult.Success)?.data
            state = state.copy(
                loading = false,
                telemetry = telemetry ?: state.telemetry,
                telemetryHistory = (historyResult as? ApiResult.Success)?.data ?: state.telemetryHistory,
                error = (telemetryResult as? ApiResult.Error)?.message,
            )
        }
    }

    LaunchedEffect(serverUrl, accessToken, device.id, historyRange) {
        refresh()
        while (true) {
            delay(5_000)
            refresh(showLoading = false)
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        RouterPageHeader(
            title = stringResource(R.string.nav_overview),
            subtitle = device.firmware.ifBlank { device.model },
            refreshing = state.loading,
            onRefresh = { refresh() },
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
    val clientCount = clients?.optInt("count", 0) ?: 0
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
    TrafficMonitorCard(history, historyRange, onHistoryRangeChange)
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
) {
    val latest = points.lastOrNull()
    SectionCard(
        title = stringResource(R.string.live_traffic),
        subtitle = stringResource(R.string.live_update_interval),
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
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            listOf(
                "live" to stringResource(R.string.telemetry_range_live),
                "24h" to stringResource(R.string.telemetry_range_day),
                "7d" to stringResource(R.string.telemetry_range_week),
                "30d" to stringResource(R.string.telemetry_range_month),
            ).forEach { (value, label) ->
                FilterChip(
                    selected = historyRange == value,
                    onClick = { onHistoryRangeChange(value) },
                    label = { Text(label) },
                    modifier = Modifier.weight(1f),
                )
            }
        }
        TrafficChart(points)
        Text(
            stringResource(R.string.telemetry_points, points.size),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.align(Alignment.End),
        )
    }
}

@Composable
private fun TrafficChart(points: List<TelemetryHistoryPointDto>) {
    val primary = MaterialTheme.colorScheme.primary
    val secondary = MaterialTheme.colorScheme.secondary
    val grid = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f)
    val visible = points
    Box(
        Modifier
            .fillMaxWidth()
            .height(156.dp)
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.36f), RoundedCornerShape(6.dp)),
        contentAlignment = Alignment.Center,
    ) {
        if (visible.size < 2) {
            Text(stringResource(R.string.collecting_data), color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            Canvas(Modifier.fillMaxWidth().height(156.dp).padding(10.dp)) {
                repeat(4) { row ->
                    val y = size.height * row / 3f
                    drawLine(grid, Offset(0f, y), Offset(size.width, y), strokeWidth = 1f)
                }
                val maximum = visible.maxOf { maxOf(it.rxBps, it.txBps) }.coerceAtLeast(1).toFloat()
                fun buildPath(selector: (TelemetryHistoryPointDto) -> Long): Path {
                    val path = Path()
                    visible.forEachIndexed { index, point ->
                        val x = size.width * index / (visible.size - 1).toFloat()
                        val y = size.height - size.height * selector(point).toFloat() / maximum
                        if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
                    }
                    return path
                }
                drawPath(buildPath { it.rxBps }, primary, style = Stroke(3f, cap = StrokeCap.Round))
                drawPath(buildPath { it.txBps }, secondary, style = Stroke(3f, cap = StrokeCap.Round))
            }
        }
    }
}

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
