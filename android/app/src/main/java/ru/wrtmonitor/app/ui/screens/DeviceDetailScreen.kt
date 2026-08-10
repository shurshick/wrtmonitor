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
import androidx.lifecycle.viewmodel.compose.viewModel
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.dto.AgentStatusDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.EventDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.dto.TelemetryHistoryPointDto
import ru.wrtmonitor.app.data.RouterRepository
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
import ru.wrtmonitor.app.viewmodel.DeviceDetailViewModel
import ru.wrtmonitor.app.viewmodel.RouterViewModelFactory
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
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
    val viewModel: DeviceDetailViewModel = viewModel(
        key = "device:${device.id}:$serverUrl:$accessToken",
        factory = RouterViewModelFactory {
            DeviceDetailViewModel(RouterRepository(serverUrl, accessToken), device)
        },
    )
    val state = viewModel.state
    val historyRange = viewModel.historyRange

    LaunchedEffect(serverUrl, accessToken, device.id) {
        viewModel.start()
    }
    LaunchedEffect(state.sessionExpired) {
        if (state.sessionExpired) onSessionExpired()
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        RouterPageHeader(
            title = stringResource(R.string.nav_overview),
            subtitle = device.firmware.ifBlank { device.model },
            refreshing = state.loading,
            onRefresh = viewModel::refresh,
        )
        when {
            state.loading -> Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            state.error != null && state.telemetry == null -> Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error)
            state.telemetry == null -> Text(stringResource(R.string.no_data))
            else -> RouterOverview(
                device,
                state.telemetry,
                state.telemetryHistory,
                historyRange,
                viewModel::selectHistoryRange,
                state.telemetryHistoryLoading,
                state.telemetryHistoryError,
                state.loadedTelemetryRange,
                state.events,
                state.quickActionRunning,
                state.quickActionMessage,
                state.quickActionError,
                viewModel::runQuickCommand,
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
    events: List<EventDto>,
    quickActionRunning: Boolean,
    quickActionMessage: String?,
    quickActionError: Boolean,
    onQuickCommand: (String, JsonObject, String) -> Unit,
    onOpenClients: () -> Unit,
    onOpenWifi: () -> Unit,
    onOpenNetwork: () -> Unit,
    onOpenSystem: () -> Unit,
) {
    val payload = telemetry.payload
    val system = payload?.optJsonObject("system")
    val memory = system?.optJsonObject("memory")
    val network = telemetry.network ?: payload?.optJsonObject("network")
    val interfaces = network?.optJsonArray("interfaces") ?: network?.optJsonArray("interface")
    var wan: JsonObject? = null
    if (interfaces != null) {
        for (index in 0 until interfaces.length()) {
            interfaces.optJsonObject(index)?.takeIf { it.optString("interface") == "wan" }?.let { wan = it }
        }
    }
    val wanUp = wan?.optBoolean("up", false) == true
    val wanAddress = wan?.optJsonArray("ipv4")?.optString(0).orEmpty().ifBlank { stringResource(R.string.no_ip_address) }
    val clients = telemetry.clients ?: payload?.optJsonObject("clients")
    val clientCount = clients?.optInt("online_count", clients.optInt("count", 0)) ?: 0
    val wifi = telemetry.wifi ?: payload?.optJsonObject("wifi")
    val radios = wifi?.optJsonArray("radios")
    val firstRadio = radios?.optJsonObject(0)
    val firstWifi = firstRadio?.optJsonArray("interfaces")?.optJsonObject(0)
    var guestWifi: JsonObject? = null
    if (radios != null) {
        for (radioIndex in 0 until radios.length()) {
            val radio = radios.optJsonObject(radioIndex) ?: continue
            val wifiInterfaces = radio.optJsonArray("interfaces") ?: continue
            for (interfaceIndex in 0 until wifiInterfaces.length()) {
                val candidate = wifiInterfaces.optJsonObject(interfaceIndex) ?: continue
                if (candidate.optString("network") == "wrtmonitor_guest" || candidate.optString("section") == "wrtmonitor_guest") {
                    guestWifi = candidate
                }
            }
        }
    }
    val guestConfig = guestWifi
    val radioId = firstRadio?.optString("name").orEmpty().ifBlank { firstRadio?.optString("id").orEmpty() }
    val wifiEnabled = firstRadio != null && !firstRadio.optBoolean("disabled", false)
    val guestEnabled = guestConfig != null && !guestConfig.optBoolean("disabled", false)
    val wifiLabel = firstWifi?.optString("ssid").orEmpty().ifBlank { stringResource(R.string.wifi_unavailable) }
    val uptime = system?.optLong("uptime", 0) ?: 0
    val availableMb = memory?.optLong("available_kb", 0)?.div(1024) ?: 0
    val totalMb = memory?.optLong("total_kb", 0)?.div(1024) ?: 0
    val memoryPercent = if (totalMb > 0) ((totalMb - availableMb).toDouble() / totalMb * 100).coerceIn(0.0, 100.0) else 0.0
    val load = system?.optString("load")?.toDoubleOrNull() ?: history.lastOrNull()?.load1m
    val cpuCores = payload?.optJsonObject("cpu")?.optInt("cores", 0)?.takeIf { it > 0 }
    val loadCapacityPercent = if (load != null && cpuCores != null) {
        (load / cpuCores * 100).coerceAtLeast(0.0).toInt()
    } else null
    val loadLevel = when {
        loadCapacityPercent == null -> null
        loadCapacityPercent < 50 -> stringResource(R.string.load_low)
        loadCapacityPercent < 100 -> stringResource(R.string.load_moderate)
        else -> stringResource(R.string.load_high)
    }
    val loadDisplay = if (load != null && cpuCores != null && loadCapacityPercent != null && loadLevel != null) {
        stringResource(R.string.load_capacity_value, loadCapacityPercent, loadLevel, load, cpuCores)
    } else stringResource(R.string.no_data)

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
    telemetry.health?.let { health ->
        val labels = listOf(
            "wan" to stringResource(R.string.health_internet),
            "dns" to stringResource(R.string.health_dns),
            "wifi" to stringResource(R.string.health_wifi),
            "agent" to stringResource(R.string.health_agent),
            "temperature" to stringResource(R.string.health_temperature),
            "memory" to stringResource(R.string.health_memory),
            "storage" to stringResource(R.string.health_storage),
        )
        SectionCard(title = stringResource(R.string.router_health)) {
            labels.forEach { (key, title) ->
                health.items[key]?.let { item ->
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(title, style = MaterialTheme.typography.labelLarge)
                            Text(item.detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        StatusPill(item.label, item.state == "ok")
                    }
                }
            }
        }
    }
    var confirmReboot by rememberSaveable { mutableStateOf(false) }
    val wifiQueuedMessage = if (wifiEnabled) stringResource(R.string.wifi_disable_queued) else stringResource(R.string.wifi_enable_queued)
    val guestQueuedMessage = if (guestEnabled) stringResource(R.string.guest_wifi_disable_queued) else stringResource(R.string.guest_wifi_enable_queued)
    val diagnosticsQueuedMessage = stringResource(R.string.diagnostics_queued)
    val rebootQueuedMessage = stringResource(R.string.reboot_queued)
    SectionCard(title = stringResource(R.string.quick_actions), subtitle = stringResource(R.string.quick_actions_summary)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SecondaryActionButton(
                if (wifiEnabled) stringResource(R.string.turn_off_wifi) else stringResource(R.string.turn_on_wifi),
                { onQuickCommand("wifi.set_enabled", JsonObject().put("enabled", !wifiEnabled).put("radio", radioId), wifiQueuedMessage) },
                Modifier.weight(1f),
                enabled = !quickActionRunning && radioId.isNotBlank(),
            )
            SecondaryActionButton(
                if (guestConfig == null) stringResource(R.string.configure_guest_wifi) else if (guestEnabled) stringResource(R.string.turn_off_guest_wifi) else stringResource(R.string.turn_on_guest_wifi),
                {
                    if (guestConfig == null) onOpenWifi() else onQuickCommand(
                        "wifi.set_guest",
                        JsonObject().put("enabled", !guestEnabled).put("radio", guestConfig.optString("device").ifBlank { radioId }).put("ssid", guestConfig.optString("ssid")),
                        guestQueuedMessage,
                    )
                },
                Modifier.weight(1f),
                enabled = !quickActionRunning,
            )
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TonalActionButton(stringResource(R.string.block_client), onOpenClients, Modifier.weight(1f), !quickActionRunning)
            TonalActionButton(
                stringResource(R.string.run_network_check),
                { onQuickCommand("diagnostics.run", JsonObject().put("checks", ru.wrtmonitor.app.api.dto.JsonArray(listOf("server", "dns", "route", "wifi", "dependencies"))), diagnosticsQueuedMessage) },
                Modifier.weight(1f),
                enabled = !quickActionRunning,
            )
        }
        SecondaryActionButton(stringResource(R.string.reboot), { confirmReboot = true }, Modifier.align(Alignment.End), !quickActionRunning)
        quickActionMessage?.let { MessageBanner(it, error = quickActionError) }
    }
    if (confirmReboot) AlertDialog(
        onDismissRequest = { confirmReboot = false },
        title = { Text(stringResource(R.string.reboot_confirm_title)) },
        text = { Text(stringResource(R.string.reboot_confirm_message)) },
        confirmButton = { TextButton(onClick = { confirmReboot = false; onQuickCommand("router.reboot", JsonObject(), rebootQueuedMessage) }) { Text(stringResource(R.string.reboot)) } },
        dismissButton = { TextButton(onClick = { confirmReboot = false }) { Text(stringResource(R.string.cancel)) } },
    )
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
            MetricTile(stringResource(R.string.system_load), loadDisplay, Modifier.weight(1f), MaterialTheme.colorScheme.tertiary)
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
    SectionCard(title = stringResource(R.string.recent_events), subtitle = stringResource(R.string.recent_events_summary)) {
        if (events.isEmpty()) Text(stringResource(R.string.no_events), color = MaterialTheme.colorScheme.onSurfaceVariant)
        events.forEach { event ->
            val severityLabel = when (event.severity) {
                "critical" -> stringResource(R.string.event_severity_critical)
                "warning" -> stringResource(R.string.event_severity_warning)
                else -> stringResource(R.string.event_severity_info)
            }
            ActionRow {
                Column(Modifier.weight(1f)) {
                    Text(event.title, style = MaterialTheme.typography.titleSmall)
                    Text(
                        listOfNotNull(event.message.takeIf(String::isNotBlank), formatTimestamp(event.lastOccurredAt)).joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                StatusPill(severityLabel, event.severity != "critical")
            }
        }
    }
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
    onRotateToken: () -> Unit,
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
    if (capabilities["agent.update"] == true || capabilities["agent.set_interval"] == true || capabilities["agent.rollback"] == true || capabilities["agent.rotate_token"] == true) {
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
            if (capabilities["agent.rotate_token"] == true) {
                SecondaryActionButton(stringResource(R.string.rotate_agent_token), onRotateToken, Modifier.align(Alignment.End))
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
