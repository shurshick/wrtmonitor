package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.FilledTonalButton
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.AgentStatusDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.ui.components.InfoRow
import ru.wrtmonitor.app.ui.components.DestinationRow
import ru.wrtmonitor.app.ui.components.ActionRow
import ru.wrtmonitor.app.ui.components.ExpandableSettingsCard
import ru.wrtmonitor.app.ui.components.MessageBanner
import ru.wrtmonitor.app.ui.components.MetricTile
import ru.wrtmonitor.app.ui.components.RouterPageHeader
import ru.wrtmonitor.app.ui.components.SectionCard
import ru.wrtmonitor.app.ui.components.StatusPill
import ru.wrtmonitor.app.ui.components.SwitchSettingRow
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
    fun refresh() {
        state = state.copy(loading = true, error = null)
        scope.launch {
            val telemetryResult = withContext(Dispatchers.IO) {
                WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id)
            }
            if (telemetryResult is ApiResult.Error && telemetryResult.isUnauthorized()) {
                onSessionExpired()
                return@launch
            }
            val telemetry = (telemetryResult as? ApiResult.Success)?.data
            state = state.copy(
                loading = false,
                telemetry = telemetry,
                error = (telemetryResult as? ApiResult.Error)?.message,
            )
        }
    }

    LaunchedEffect(serverUrl, accessToken, device.id) { refresh() }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        RouterPageHeader(
            title = stringResource(R.string.nav_overview),
            subtitle = device.firmware.ifBlank { device.model },
            refreshing = state.loading,
            onRefresh = ::refresh,
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

    val healthy = device.status == "online" && !telemetry.isStale
    SectionCard(
        title = if (healthy) stringResource(R.string.router_healthy) else stringResource(R.string.router_attention),
        subtitle = stringResource(R.string.last_contact_value, formatTimestamp(telemetry.createdAt) ?: stringResource(R.string.no_data)),
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(device.model, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            StatusPill(if (healthy) stringResource(R.string.online) else stringResource(R.string.offline), healthy)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            MetricTile(stringResource(R.string.uptime), formatDuration(uptime), Modifier.weight(1f))
            MetricTile(
                stringResource(R.string.memory),
                stringResource(R.string.memory_value_mb, availableMb, totalMb),
                Modifier.weight(1f),
                MaterialTheme.colorScheme.secondary,
            )
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
                FilledTonalButton(onClick = onCheckUpdate, modifier = Modifier.align(Alignment.End)) {
                    Text(stringResource(R.string.check_update))
                }
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
                Button(
                    onClick = { intervalValue?.let(onSetInterval) },
                    modifier = Modifier.align(Alignment.End),
                    enabled = intervalValue != null && intervalValue >= 5,
                ) { Text(stringResource(R.string.change_interval)) }
            }
            if (capabilities["agent.rollback"] == true) {
                OutlinedButton(onClick = onRollback, modifier = Modifier.align(Alignment.End)) {
                    Text(stringResource(R.string.rollback_action))
                }
            }
        }
    }
    if (capabilities.isNotEmpty()) {
        ExpandableSettingsCard(
            title = stringResource(R.string.capabilities),
            summary = capabilitiesSummary(capabilities),
        ) {
            groupedCapabilities(capabilities).forEach { (title, values) ->
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
