package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.ui.components.InfoRow
import ru.wrtmonitor.app.viewmodel.DeviceDetailUiState

@Composable
fun DeviceDetailScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    var state by remember(device.id) { mutableStateOf(DeviceDetailUiState(loading = true, device = device)) }
    fun refresh() {
        state = state.copy(loading = true, error = null)
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> state = state.copy(loading = false, telemetry = result.data)
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else state = state.copy(loading = false, error = result.message)
            }
        }
    }
    LaunchedEffect(serverUrl, accessToken, device.id) { refresh() }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(device.name.ifBlank { device.hostname }, style = MaterialTheme.typography.titleLarge)
                InfoRow(stringResource(R.string.model), device.model, stringResource(R.string.no_data))
                InfoRow(stringResource(R.string.firmware), device.firmware, stringResource(R.string.no_data))
                InfoRow(stringResource(R.string.status), device.status, stringResource(R.string.no_data))
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.telemetry), style = MaterialTheme.typography.titleLarge)
            Button({ refresh() }, enabled = !state.loading) { Text(stringResource(R.string.refresh)) }
        }
        when {
            state.loading -> Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            state.error != null -> Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error)
            state.telemetry == null -> Text(stringResource(R.string.no_data))
            else -> TelemetrySummary(state.telemetry!!)
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
    val network = payload.optJSONObject("network")
    val networkDevices = payload.optJSONObject("network_devices")
    val interfaces = network?.optJSONArray("interface") ?: network?.optJSONArray("interfaces")
    val wifi = payload.optJSONObject("wifi")
    val radios = wifi?.optJSONArray("radios")
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        TelemetrySection("Состояние") {
            InfoRow(stringResource(R.string.updated_at), telemetry.createdAt, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.age), telemetry.ageSeconds?.let { "$it сек" }, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.source), telemetry.source, stringResource(R.string.no_data))
            if (telemetry.isStale) Text(stringResource(R.string.stale_telemetry), color = MaterialTheme.colorScheme.error)
        }
        TelemetrySection("Система") {
            InfoRow(stringResource(R.string.uptime), formatDuration(system?.optLong("uptime", 0) ?: 0))
            InfoRow(stringResource(R.string.load), system?.optString("load"), stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.memory), memory?.let { memoryLabel(it) }, stringResource(R.string.no_data))
            InfoRow("Процессор", cpu?.optString("model").orEmpty().ifBlank { "Не определён" })
            InfoRow("Ядра CPU", cpu?.optLong("cores", 0)?.takeIf { it > 0 }?.toString(), stringResource(R.string.no_data))
            InfoRow("Накопитель", storage?.let { storageLabel(it) }, stringResource(R.string.no_data))
            InfoRow("Температура", thermalLabel(thermal), stringResource(R.string.no_data))
            InfoRow("Процессы", processes?.optLong("count", 0)?.takeIf { it > 0 }?.toString(), stringResource(R.string.no_data))
        }
        TelemetrySection("Оборудование") {
            InfoRow(stringResource(R.string.model), board?.optString("model").orEmpty().ifBlank { null }, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.firmware), release?.optString("description").orEmpty().ifBlank { release?.optString("version") }, stringResource(R.string.no_data))
        }
        TelemetrySection("Сеть") {
            InfoRow("RX / TX", traffic?.let { "${formatBytes(it.optLong("rx_bytes"))} / ${formatBytes(it.optLong("tx_bytes"))}" }, stringResource(R.string.no_data))
            if (interfaces == null || interfaces.length() == 0) Text("Агент ещё не передал интерфейсы") else InterfaceRows(interfaces)
            if (networkDevices != null) NetworkDeviceRows(networkDevices)
        }
        TelemetrySection("Wi-Fi") {
            if (wifi?.optBoolean("available", false) != true) Text(stringResource(R.string.wifi_unavailable)) else RadioRows(radios)
        }
    }
}

@Composable
private fun TelemetrySection(title: String, content: @Composable () -> Unit) {
    Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) { Text(title, style = MaterialTheme.typography.titleMedium); content() } }
}

@Composable
private fun InterfaceRows(interfaces: JSONArray) {
    for (index in 0 until interfaces.length()) {
        val item = interfaces.optJSONObject(index) ?: continue
        val name = item.optString("interface", item.optString("name", "interface"))
        val state = if (item.optBoolean("up", false)) "В сети" else "Не в сети"
        val address = firstAddress(item.optJSONArray("ipv4-address"))
        InfoRow(name, listOf(state, address).filter { it.isNotBlank() }.joinToString(" · "))
    }
}

@Composable
private fun RadioRows(radios: JSONArray?) {
    if (radios == null || radios.length() == 0) { Text(stringResource(R.string.wifi_unavailable)); return }
    for (index in 0 until radios.length()) {
        val radio = radios.optJSONObject(index) ?: continue
        val name = radio.optString("name", "radio$index")
        val ssid = radio.optJSONArray("ssid")?.optString(0).orEmpty()
        val details = listOf(if (radio.optBoolean("up", false)) "Включён" else "Выключен", ssid, radio.optString("band"), radio.optString("channel")).filter { it.isNotBlank() }.joinToString(" · ")
        InfoRow(name, details)
    }
}

@Composable
private fun NetworkDeviceRows(devices: JSONObject) {
    val names = devices.keys().asSequence().toList().sorted()
    for (name in names) {
        val item = devices.optJSONObject(name) ?: continue
        val details = listOf(
            if (item.optBoolean("up", false)) "Активен" else "Неактивен",
            item.optBoolean("carrier", false).let { if (it) "carrier есть" else "carrier нет" },
            item.optLong("mtu", 0).takeIf { it > 0 }?.let { "MTU $it" }.orEmpty()
        ).filter { it.isNotBlank() }.joinToString(" · ")
        InfoRow(name, details)
    }
}

private fun firstAddress(addresses: JSONArray?): String = addresses?.optJSONObject(0)?.optString("address").orEmpty()
private fun memoryLabel(memory: JSONObject): String = "${memory.optLong("available_kb") / 1024} / ${memory.optLong("total_kb") / 1024} MB"
private fun storageLabel(storage: JSONObject): String = "${storage.optLong("used_kb") / 1024} использовано, ${storage.optLong("available_kb") / 1024} MB свободно"
private fun thermalLabel(thermal: JSONObject?): String? = if (thermal?.optBoolean("available", false) == true) "${thermal.optLong("milli_celsius") / 1000.0} °C" else null
private fun formatBytes(bytes: Long): String = when { bytes >= 1_073_741_824 -> "%.1f GB".format(bytes / 1_073_741_824.0); bytes >= 1_048_576 -> "%.1f MB".format(bytes / 1_048_576.0); bytes >= 1024 -> "%.1f KB".format(bytes / 1024.0); else -> "$bytes B" }
private fun formatDuration(seconds: Long): String { val days = seconds / 86_400; val hours = (seconds % 86_400) / 3_600; val minutes = (seconds % 3_600) / 60; return listOfNotNull(days.takeIf { it > 0 }?.let { "$it д" }, hours.takeIf { it > 0 }?.let { "$it ч" }, minutes.let { "$it мин" }).joinToString(" ") }
