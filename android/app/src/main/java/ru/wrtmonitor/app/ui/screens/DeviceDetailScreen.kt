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
import androidx.compose.ui.res.stringResource
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
    onArchived: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var state by remember(device.id) {
        mutableStateOf(DeviceDetailUiState(loading = true, device = device))
    }
    var actionMessage by remember(device.id) { mutableStateOf("") }
    var actionError by remember(device.id) { mutableStateOf("") }
    var confirmRollback by remember(device.id) { mutableStateOf(false) }
    var confirmArchive by remember(device.id) { mutableStateOf(false) }

    fun refresh() {
        state = state.copy(loading = true, error = null)
        actionError = ""
        scope.launch {
            val api = WrtMonitorApi(serverUrl, accessToken)
            val telemetryResult = withContext(Dispatchers.IO) { api.getLatestTelemetry(device.id) }
            if (telemetryResult is ApiResult.Error && telemetryResult.isUnauthorized()) {
                onSessionExpired()
                return@launch
            }
            val agentResult = withContext(Dispatchers.IO) { api.getDeviceAgent(device.id) }
            if (agentResult is ApiResult.Error && agentResult.isUnauthorized()) {
                onSessionExpired()
                return@launch
            }
            val telemetry = (telemetryResult as? ApiResult.Success)?.data
            val agent = (agentResult as? ApiResult.Success)?.data ?: telemetry?.agent
            val error = (telemetryResult as? ApiResult.Error)?.message ?: (agentResult as? ApiResult.Error)?.message
            state = state.copy(
                loading = false,
                telemetry = telemetry?.copy(agent = agent ?: telemetry.agent),
                error = error,
            )
        }
    }

    fun queueCommand(type: String, payload: JSONObject = JSONObject(), success: String) {
        actionMessage = ""
        actionError = ""
        scope.launch {
            when (val result = withContext(Dispatchers.IO) {
                WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, type, payload, confirmed = true)
            }) {
                is ApiResult.Success -> {
                    actionMessage = success
                    refresh()
                }
                is ApiResult.Error -> {
                    if (result.isUnauthorized()) onSessionExpired() else actionError = result.message
                }
            }
        }
    }

    fun archiveDevice() {
        actionMessage = ""
        actionError = ""
        scope.launch {
            when (val result = withContext(Dispatchers.IO) {
                WrtMonitorApi(serverUrl, accessToken).archiveDevice(device.id)
            }) {
                is ApiResult.Success -> onArchived()
                is ApiResult.Error -> {
                    if (result.isUnauthorized()) onSessionExpired() else actionError = result.message
                }
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
                InfoRow(stringResource(R.string.last_seen), formatTimestamp(device.lastSeenAt), stringResource(R.string.no_data))
            }
        }
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(stringResource(R.string.telemetry), style = MaterialTheme.typography.titleLarge)
            Button({ refresh() }, enabled = !state.loading) { Text(stringResource(R.string.refresh)) }
        }
        when {
            state.loading -> Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            state.error != null && state.telemetry == null -> Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error)
            state.telemetry == null -> Text(stringResource(R.string.no_data))
            else -> TelemetrySummary(state.telemetry!!)
        }
        AgentSection(
            agent = state.telemetry?.agent,
            actionMessage = actionMessage,
            actionError = actionError,
            canArchive = device.status == "disabled",
            onCheckUpdate = { queueCommand("agent.update", success = "Команда проверки обновления добавлена") },
            onSetInterval = { seconds ->
                queueCommand(
                    "agent.set_interval",
                    JSONObject().put("interval_seconds", seconds),
                    "Новый интервал telemetry будет применён при следующем цикле агента",
                )
            },
            onEnableAutoUpdate = { queueCommand("agent.set_auto_update", JSONObject().put("enabled", true), "Автообновление будет включено при следующем опросе агента") },
            onDisableAutoUpdate = { queueCommand("agent.set_auto_update", JSONObject().put("enabled", false), "Автообновление будет выключено при следующем опросе агента") },
            onRollback = { confirmRollback = true },
            onArchive = { confirmArchive = true },
        )
    }

    if (confirmRollback) {
        AlertDialog(
            onDismissRequest = { confirmRollback = false },
            title = { Text("Вернуть предыдущую версию агента?") },
            text = { Text("Агент попробует восстановить предыдущую рабочую версию и перезапуститься.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmRollback = false
                    queueCommand("agent.rollback", success = "Команда rollback добавлена")
                }) { Text("Rollback") }
            },
            dismissButton = {
                TextButton(onClick = { confirmRollback = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    if (confirmArchive) {
        AlertDialog(
            onDismissRequest = { confirmArchive = false },
            title = { Text("Удалить из списка?") },
            text = { Text("Этот роутер уже отключён. История telemetry и команд останется на сервере, но для повторного подключения агент нужно будет зарегистрировать заново.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmArchive = false
                    archiveDevice()
                }) { Text("Удалить") }
            },
            dismissButton = {
                TextButton(onClick = { confirmArchive = false }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
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
        TelemetrySection("Состояние") {
            InfoRow(stringResource(R.string.updated_at), formatTimestamp(telemetry.createdAt), stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.age), telemetry.ageSeconds?.let { "$it сек" }, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.source), telemetry.source, stringResource(R.string.no_data))
            if (telemetry.isStale) {
                Text(stringResource(R.string.stale_telemetry), color = MaterialTheme.colorScheme.error)
            }
        }
        TelemetrySection("Система") {
            InfoRow(stringResource(R.string.uptime), formatDuration(system?.optLong("uptime", 0) ?: 0))
            InfoRow(stringResource(R.string.load), system?.optString("load"), stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.memory), memory?.let { memoryLabel(it) }, stringResource(R.string.no_data))
            InfoRow("Процессор", cpu?.optString("model").orEmpty().ifBlank { "Не определен" })
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
            if (interfaces == null || interfaces.length() == 0) {
                Text("Агент еще не передал интерфейсы")
            } else {
                InterfaceRows(interfaces)
            }
            if (networkDevices != null) NetworkDeviceRows(networkDevices)
        }
        TelemetrySection("Wi-Fi") {
            if (wifi?.optBoolean("available", false) != true) Text(stringResource(R.string.wifi_unavailable)) else RadioRows(radios)
        }
    }
}

@Composable
private fun AgentSection(
    agent: AgentStatusDto?,
    actionMessage: String,
    actionError: String,
    canArchive: Boolean,
    onCheckUpdate: () -> Unit,
    onSetInterval: (Int) -> Unit,
    onEnableAutoUpdate: () -> Unit,
    onDisableAutoUpdate: () -> Unit,
    onRollback: () -> Unit,
    onArchive: () -> Unit,
) {
    val capabilities = agent?.capabilities ?: emptyMap()
    val autoUpdateEnabled = agent?.autoUpdateEnabled == true
    var showCapabilities by rememberSaveable { mutableStateOf(false) }
    var intervalInput by rememberSaveable(agent?.telemetryIntervalSeconds) {
        mutableStateOf(agent?.telemetryIntervalSeconds?.toString() ?: "60")
    }
    val intervalValue = intervalInput.toIntOrNull()
    val intervalError = intervalInput.isNotBlank() && (intervalValue == null || intervalValue < 5)
    TelemetrySection("Агент") {
        InfoRow("Версия", agent?.version, stringResource(R.string.no_data))
        InfoRow("Статус", agent?.status, stringResource(R.string.no_data))
        InfoRow("Автообновление", if (agent == null) null else if (autoUpdateEnabled) "Включено" else "Выключено", stringResource(R.string.no_data))
        InfoRow("Интервал telemetry", agent?.telemetryIntervalSeconds?.let { "$it сек" }, stringResource(R.string.no_data))
        InfoRow("Доступная версия", agent?.availableVersion, stringResource(R.string.no_data))
        InfoRow("Последняя проверка", formatTimestamp(agent?.lastUpdateCheck), stringResource(R.string.no_data))
        InfoRow("Статус обновления", agent?.lastUpdateStatus, stringResource(R.string.no_data))
        InfoRow("Последнее успешное обновление", formatTimestamp(agent?.lastSuccessfulUpdate), stringResource(R.string.no_data))
        InfoRow("Последняя ошибка", agent?.lastUpdateError, stringResource(R.string.no_data))
        InfoRow("Rollback", if (agent == null) null else if (agent.rollbackAvailable) "Доступен" else "Нет", stringResource(R.string.no_data))
        InfoRow("Источник", agent?.updateSource, stringResource(R.string.no_data))
        InfoRow("Capabilities", capabilitiesSummary(capabilities), stringResource(R.string.no_data))
        if (capabilities.isNotEmpty()) {
            TextButton(onClick = { showCapabilities = !showCapabilities }, modifier = Modifier.fillMaxWidth()) {
                Text(if (showCapabilities) "Скрыть capabilities" else "Показать capabilities")
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
            Button(onClick = onCheckUpdate, modifier = Modifier.fillMaxWidth()) { Text("Проверить обновление") }
        }
        if (capabilities["agent.update"] == true) {
            Button(
                onClick = if (autoUpdateEnabled) onDisableAutoUpdate else onEnableAutoUpdate,
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (autoUpdateEnabled) "Выключить автообновление" else "Включить автообновление") }
        }
        if (capabilities["agent.set_interval"] == true) {
            OutlinedTextField(
                value = intervalInput,
                onValueChange = { value -> intervalInput = value.filter(Char::isDigit) },
                label = { Text("Интервал telemetry, сек") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                isError = intervalError,
                supportingText = { Text(if (intervalError) "Минимум 5 секунд" else "Минимум 5 секунд") },
            )
            Button(
                onClick = { intervalValue?.let(onSetInterval) },
                modifier = Modifier.fillMaxWidth(),
                enabled = intervalValue != null && intervalValue >= 5,
            ) { Text("Изменить интервал") }
        }
        if (capabilities["agent.rollback"] == true) {
            Button(onClick = onRollback, modifier = Modifier.fillMaxWidth()) { Text("Rollback agent") }
        }
        if (capabilities.isEmpty()) {
            Text(
                "Агент ещё не передал capabilities. Для управления установите агент rc9 заново.",
                color = MaterialTheme.colorScheme.secondary,
            )
        }
        if (canArchive) {
            TextButton(onClick = onArchive, modifier = Modifier.fillMaxWidth()) {
                Text("Удалить из списка", color = MaterialTheme.colorScheme.error)
            }
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
        val state = if (item.optBoolean("up", false)) "В сети" else "Не в сети"
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
            if (radio.optBoolean("up", false)) "Включен" else "Выключен",
            radio.optString("band").takeIf { it.isNotBlank() },
            radio.optString("channel").takeIf { it.isNotBlank() }?.let { "канал $it" },
        ).joinToString(" · ")
        InfoRow(name, details)
        val interfaces = radio.optJSONArray("interfaces")
        if (interfaces != null) {
            for (ifaceIndex in 0 until interfaces.length()) {
                val iface = interfaces.optJSONObject(ifaceIndex) ?: continue
                InfoRow(
                    "SSID ${ifaceIndex + 1}",
                    listOfNotNull(
                        iface.optString("ssid").takeIf { it.isNotBlank() },
                        if (iface.optBoolean("enabled", true)) "активен" else "выключен",
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
            if (item.optBoolean("up", false)) "Активен" else "Неактивен",
            if (item.optBoolean("carrier", false)) "carrier есть" else "carrier нет",
            item.optLong("mtu", 0).takeIf { it > 0 }?.let { "MTU $it" }.orEmpty(),
        ).filter { it.isNotBlank() }.joinToString(" · ")
        InfoRow(name, details)
    }
}

private fun firstAddress(addresses: JSONArray?): String =
    addresses?.optJSONObject(0)?.optString("address").orEmpty()

private fun memoryLabel(memory: JSONObject): String =
    "${memory.optLong("available_kb") / 1024} / ${memory.optLong("total_kb") / 1024} MB"

private fun storageLabel(storage: JSONObject): String =
    "${storage.optLong("used_kb") / 1024} использовано, ${storage.optLong("available_kb") / 1024} MB свободно"

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

private fun formatDuration(seconds: Long): String {
    val days = seconds / 86_400
    val hours = (seconds % 86_400) / 3_600
    val minutes = (seconds % 3_600) / 60
    return listOfNotNull(
        days.takeIf { it > 0 }?.let { "$it д" },
        hours.takeIf { it > 0 }?.let { "$it ч" },
        minutes.let { "$it мин" },
    ).joinToString(" ")
}
