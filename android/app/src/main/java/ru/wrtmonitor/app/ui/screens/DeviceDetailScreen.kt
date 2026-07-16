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
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.AgentStatusDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.ui.components.InfoRow
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
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(device.name.ifBlank { device.hostname }, style = MaterialTheme.typography.headlineSmall)
                Text(device.model, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Button({ refresh() }, enabled = !state.loading) { Text(stringResource(R.string.refresh)) }
        }
        when {
            state.loading -> Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            state.error != null && state.telemetry == null -> Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error)
            state.telemetry == null -> Text(stringResource(R.string.no_data))
            else -> RouterOverview(device, state.telemetry!!)
        }
    }

}

@Composable
private fun RouterOverview(device: DeviceDto, telemetry: TelemetryDto) {
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

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(
                if (device.status == "online" && !telemetry.isStale) stringResource(R.string.router_healthy) else stringResource(R.string.router_attention),
                style = MaterialTheme.typography.titleLarge,
                color = if (device.status == "online" && !telemetry.isStale) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.tertiary,
            )
            Text(device.firmware.ifBlank { stringResource(R.string.no_data) }, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(
                stringResource(R.string.last_contact_value, formatTimestamp(telemetry.createdAt) ?: stringResource(R.string.no_data)),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        OverviewTile(
            title = stringResource(R.string.internet),
            value = if (wanUp) stringResource(R.string.connected) else stringResource(R.string.disconnected),
            detail = wanAddress,
            accent = if (wanUp) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.error,
            modifier = Modifier.weight(1f),
        )
        OverviewTile(
            title = stringResource(R.string.home_network),
            value = clientCount.toString(),
            detail = stringResource(R.string.connected_devices),
            accent = Color(0xFF73D596),
            modifier = Modifier.weight(1f),
        )
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        OverviewTile(
            title = stringResource(R.string.wifi),
            value = wifiLabel,
            detail = stringResource(R.string.radio_count_value, radios?.length() ?: 0),
            accent = Color(0xFF6FA8FF),
            modifier = Modifier.weight(1f),
        )
        OverviewTile(
            title = stringResource(R.string.system),
            value = formatDuration(uptime),
            detail = stringResource(R.string.memory_value_mb, availableMb, totalMb),
            accent = MaterialTheme.colorScheme.tertiary,
            modifier = Modifier.weight(1f),
        )
    }
    Text(
        stringResource(R.string.overview_navigation_hint),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
    )
}

@Composable
private fun OverviewTile(title: String, value: String, detail: String, accent: Color, modifier: Modifier = Modifier) {
    Card(modifier) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(title, style = MaterialTheme.typography.labelLarge, color = accent)
            Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, maxLines = 2)
            Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
        }
    }
}

@Composable
private fun TelemetrySummary(telemetry: TelemetryDto) {
    val payload = telemetry.payload ?: return
    val system = payload.optJSONObject("system")
    val memory = system?.optJSONObject("memory")
    val cpu = payload.optJSONObject("cpu")
    val storage = payload.optJSONObject("storage")
    val thermal = payload.optJSONObject("thermal")
    val traffic = payload.optJSONObject("traffic")
    val processes = system?.optJSONObject("processes")
    val board = payload.optJSONObject("board")
    val release = board?.optJSONObject("release")
    val network = telemetry.network ?: payload.optJSONObject("network")
    val networkDevices = payload.optJSONObject("network_devices")
    val interfaces = network?.optJSONArray("interfaces") ?: network?.optJSONArray("interface")
    val wifi = telemetry.wifi ?: payload.optJSONObject("wifi")
    val radios = wifi?.optJSONArray("radios")
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        TelemetrySection(stringResource(R.string.telemetry_state_title)) {
            InfoRow(stringResource(R.string.updated_at), formatTimestamp(telemetry.createdAt), stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.age), telemetry.ageSeconds?.let { stringResource(R.string.seconds_value, it.toInt()) }, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.source), telemetry.source, stringResource(R.string.no_data))
            if (telemetry.isStale) {
                Text(stringResource(R.string.stale_telemetry), color = MaterialTheme.colorScheme.error)
            }
        }
        TelemetrySection(stringResource(R.string.telemetry_system_title)) {
            InfoRow(stringResource(R.string.uptime), formatDuration(system?.optLong("uptime", 0) ?: 0))
            InfoRow(stringResource(R.string.load), system?.optString("load"), stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.memory), memory?.let { memoryLabel(it) }, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.cpu), cpu?.optString("model").orEmpty().ifBlank { stringResource(R.string.not_detected) }, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.cpu_cores), cpu?.optLong("cores", 0)?.takeIf { it > 0 }?.toString(), stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.storage), storage?.let { storageLabel(it) }, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.temperature), thermalLabel(thermal), stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.processes), processes?.optLong("count", 0)?.takeIf { it > 0 }?.toString(), stringResource(R.string.no_data))
        }
        TelemetrySection(stringResource(R.string.telemetry_hardware_title)) {
            InfoRow(stringResource(R.string.model), board?.optString("model").orEmpty().ifBlank { null }, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.firmware), release?.optString("description").orEmpty().ifBlank { release?.optString("version") }, stringResource(R.string.no_data))
        }
        TelemetrySection(stringResource(R.string.telemetry_network_title)) {
            InfoRow(stringResource(R.string.network_rx_tx), traffic?.let { "${formatBytes(it.optLong("rx_bytes"))} / ${formatBytes(it.optLong("tx_bytes"))}" }, stringResource(R.string.no_data))
            if (interfaces == null || interfaces.length() == 0) {
                Text(stringResource(R.string.interfaces_missing))
            } else {
                InterfaceRows(interfaces)
            }
            if (networkDevices != null) NetworkDeviceRows(networkDevices)
        }
        TelemetrySection(stringResource(R.string.telemetry_wifi_title)) {
            if (wifi?.optBoolean("available", false) != true) Text(stringResource(R.string.wifi_unavailable)) else RadioRows(radios)
        }
    }
}

@Composable
internal fun AgentSection(
    agent: AgentStatusDto?,
    actionMessage: String,
    actionError: String,
    onCheckUpdate: () -> Unit,
    onSetInterval: (Int) -> Unit,
    onEnableAutoUpdate: () -> Unit,
    onDisableAutoUpdate: () -> Unit,
    onRollback: () -> Unit,
) {
    val capabilities = agent?.capabilities ?: emptyMap()
    val autoUpdateEnabled = agent?.autoUpdateEnabled == true
    var showCapabilities by rememberSaveable { mutableStateOf(false) }
    var intervalInput by rememberSaveable(agent?.telemetryIntervalSeconds) {
        mutableStateOf(agent?.telemetryIntervalSeconds?.toString() ?: "60")
    }
    val intervalValue = intervalInput.toIntOrNull()
    val intervalError = intervalInput.isNotBlank() && (intervalValue == null || intervalValue < 5)
    TelemetrySection(stringResource(R.string.agent_section_title)) {
        InfoRow(stringResource(R.string.version), agent?.version, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.status), agent?.status, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.auto_update), if (agent == null) null else if (autoUpdateEnabled) stringResource(R.string.enabled_value) else stringResource(R.string.disabled_value), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.telemetry_interval), agent?.telemetryIntervalSeconds?.let { stringResource(R.string.seconds_value, it) }, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.available_version), agent?.availableVersion, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.last_update_check), formatTimestamp(agent?.lastUpdateCheck), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.update_status), agent?.lastUpdateStatus, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.last_successful_update), formatTimestamp(agent?.lastSuccessfulUpdate), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.last_error), agent?.lastUpdateError, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.rollback), if (agent == null) null else if (agent.rollbackAvailable) stringResource(R.string.rollback_available) else stringResource(R.string.rollback_unavailable), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.update_source), agent?.updateSource, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.capabilities), capabilitiesSummary(capabilities), stringResource(R.string.no_data))
        if (capabilities.isNotEmpty()) {
            TextButton(onClick = { showCapabilities = !showCapabilities }, modifier = Modifier.fillMaxWidth()) {
                Text(if (showCapabilities) stringResource(R.string.hide_capabilities) else stringResource(R.string.show_capabilities))
            }
            if (showCapabilities) {
                groupedCapabilities(capabilities).forEach { (title, values) ->
                    InfoRow(title, values.joinToString(", "))
                }
            }
        }

        if (actionMessage.isNotBlank()) Text(actionMessage, color = MaterialTheme.colorScheme.primary)
        if (actionError.isNotBlank()) Text(actionError, color = MaterialTheme.colorScheme.error)

        if (capabilities["agent.update"] == true) {
            Button(onClick = onCheckUpdate, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.check_update)) }
        }
        if (capabilities["agent.update"] == true) {
            Button(
                onClick = if (autoUpdateEnabled) onDisableAutoUpdate else onEnableAutoUpdate,
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (autoUpdateEnabled) stringResource(R.string.disable_auto_update) else stringResource(R.string.enable_auto_update)) }
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
                modifier = Modifier.fillMaxWidth(),
                enabled = intervalValue != null && intervalValue >= 5,
            ) { Text(stringResource(R.string.change_interval)) }
        }
        if (capabilities["agent.rollback"] == true) {
            Button(onClick = onRollback, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.rollback_action)) }
        }
        if (capabilities.isEmpty()) {
            Text(
                stringResource(R.string.capabilities_missing_reinstall),
                color = MaterialTheme.colorScheme.secondary,
            )
        }
    }
}

@Composable
private fun TelemetrySection(title: String, content: @Composable () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            content()
        }
    }
}

@Composable
private fun InterfaceRows(interfaces: JSONArray) {
    for (index in 0 until interfaces.length()) {
        val item = interfaces.optJSONObject(index) ?: continue
        val name = item.optString("interface", item.optString("name", "interface"))
        val state = if (item.optBoolean("up", false)) stringResource(R.string.in_network) else stringResource(R.string.out_of_network)
        val proto = item.optString("proto").takeIf { it.isNotBlank() }
        val device = item.optString("device").takeIf { it.isNotBlank() }
        val ipv4 = item.optJSONArray("ipv4")?.optString(0).takeIf { !it.isNullOrBlank() }
            ?: firstAddress(item.optJSONArray("ipv4-address")).takeIf { it.isNotBlank() }
        InfoRow(name, listOfNotNull(state, proto, device, ipv4).joinToString(" · "))
    }
}

@Composable
private fun RadioRows(radios: JSONArray?) {
    if (radios == null || radios.length() == 0) {
        Text(stringResource(R.string.wifi_unavailable))
        return
    }
    for (index in 0 until radios.length()) {
        val radio = radios.optJSONObject(index) ?: continue
        val name = radio.optString("name", radio.optString("id", "radio$index"))
        val details = listOfNotNull(
            if (radio.optBoolean("up", false)) stringResource(R.string.wifi_enabled_state) else stringResource(R.string.wifi_disabled_state),
            radio.optString("band").takeIf { it.isNotBlank() },
            radio.optString("channel").takeIf { it.isNotBlank() }?.let { stringResource(R.string.channel_value, it) },
        ).joinToString(" · ")
        InfoRow(name, details)
        val interfaces = radio.optJSONArray("interfaces")
        if (interfaces != null) {
            for (ifaceIndex in 0 until interfaces.length()) {
                val iface = interfaces.optJSONObject(ifaceIndex) ?: continue
                InfoRow(
                    stringResource(R.string.ssid_item, ifaceIndex + 1),
                    listOfNotNull(
                        iface.optString("ssid").takeIf { it.isNotBlank() },
                        if (iface.optBoolean("enabled", true)) stringResource(R.string.radio_active) else stringResource(R.string.radio_disabled),
                        iface.optString("encryption").takeIf { it.isNotBlank() },
                    ).joinToString(" · "),
                )
            }
        }
    }
}

@Composable
private fun NetworkDeviceRows(devices: JSONObject) {
    val names = devices.keys().asSequence().toList().sorted()
    for (name in names) {
        val item = devices.optJSONObject(name) ?: continue
        val details = listOf(
            if (item.optBoolean("up", false)) stringResource(R.string.device_active) else stringResource(R.string.device_inactive),
            if (item.optBoolean("carrier", false)) stringResource(R.string.carrier_present) else stringResource(R.string.carrier_missing),
            item.optLong("mtu", 0).takeIf { it > 0 }?.let { "MTU $it" }.orEmpty(),
        ).filter { it.isNotBlank() }.joinToString(" · ")
        InfoRow(name, details)
    }
}

private fun firstAddress(addresses: JSONArray?): String =
    addresses?.optJSONObject(0)?.optString("address").orEmpty()

private fun memoryLabel(memory: JSONObject): String =
    "${memory.optLong("available_kb") / 1024} / ${memory.optLong("total_kb") / 1024} MB"

@Composable
private fun storageLabel(storage: JSONObject): String =
    androidx.compose.ui.platform.LocalContext.current.getString(
        R.string.storage_used_free,
        storage.optLong("used_kb") / 1024,
        storage.optLong("available_kb") / 1024,
    )

private fun thermalLabel(thermal: JSONObject?): String? =
    if (thermal?.optBoolean("available", false) == true) {
        "${thermal.optLong("milli_celsius") / 1000.0} °C"
    } else {
        null
    }

private fun formatBytes(bytes: Long): String = when {
    bytes >= 1_073_741_824 -> "%.1f GB".format(bytes / 1_073_741_824.0)
    bytes >= 1_048_576 -> "%.1f MB".format(bytes / 1_048_576.0)
    bytes >= 1024 -> "%.1f KB".format(bytes / 1024.0)
    else -> "$bytes B"
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
