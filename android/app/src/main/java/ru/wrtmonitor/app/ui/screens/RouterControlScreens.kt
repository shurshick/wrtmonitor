package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.CommandDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.ui.components.InfoRow

@Composable
fun WifiControlScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var ssid by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var enabled by remember { mutableStateOf(true) }
    var message by remember { mutableStateOf("") }
    var pendingAction by remember { mutableStateOf<(() -> Unit)?>(null) }

    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    val radio = firstRadio(result.data)
                    val iface = firstInterface(result.data)
                    ssid = iface?.optString("ssid").orEmpty()
                    enabled = radio?.optBoolean("up", true) ?: true
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
            }
        }
        Unit
    }

    fun queue(type: String, payload: JSONObject, success: String) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) {
                WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, type, payload, confirmed = true)
            }) {
                is ApiResult.Success -> {
                    message = success
                    if (type == "wifi.set_password") password = ""
                    refresh()
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
            }
        }
    }

    LaunchedEffect(device.id) { refresh() }
    val wifi = telemetry?.wifi ?: telemetry?.payload?.optJSONObject("wifi")
    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()
    val radio = firstRadio(telemetry)
    val iface = firstInterface(telemetry)
    val radioId = radio?.optString("id").takeUnless { it.isNullOrBlank() } ?: "radio0"
    val ifaceId = iface?.optString("id").takeUnless { it.isNullOrBlank() }

    Text(stringResource(R.string.wifi), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            InfoRow("Статус", if (wifi?.optBoolean("available", false) == true) "Доступно" else "Нет данных")
            InfoRow("Радиомодули", wifi?.optJSONArray("radios")?.length()?.toString())
            iface?.let { InfoRow("Текущий SSID", it.optString("ssid").ifBlank { "Нет данных" }) }

            if (capabilities["wifi.set_ssid"] == true) {
                OutlinedTextField(
                    value = ssid,
                    onValueChange = { ssid = it },
                    label = { Text("SSID") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
                Button(
                    onClick = {
                        pendingAction = {
                            queue("wifi.set_ssid", JSONObject().put("ssid", ssid).put("iface", ifaceId), "Команда изменения SSID добавлена")
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = ssid.isNotBlank(),
                ) { Text("Применить SSID") }
            }

            if (capabilities["wifi.set_password"] == true) {
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Новый пароль Wi-Fi") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                )
                Button(
                    onClick = {
                        pendingAction = {
                            queue("wifi.set_password", JSONObject().put("password", password).put("iface", ifaceId), "Команда смены пароля добавлена")
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = password.length >= 8,
                ) { Text("Изменить пароль") }
            }

            if (capabilities["wifi.enable"] == true || capabilities["wifi.disable"] == true) {
                InfoRow("Wi-Fi", if (enabled) "Включен" else "Выключен")
                Switch(checked = enabled, onCheckedChange = { enabled = it })
                Button(
                    onClick = {
                        pendingAction = {
                            queue("wifi.set_enabled", JSONObject().put("enabled", enabled).put("radio", radioId), "Команда Wi-Fi добавлена")
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Применить состояние Wi-Fi") }
            }

            if (capabilities.isEmpty()) {
                Text("Старый агент: доступны только данные без управляющих действий.", color = MaterialTheme.colorScheme.secondary)
            }
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.primary)
            TextButton(onClick = refresh, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refresh)) }
        }
    }

    pendingAction?.let { action ->
        AlertDialog(
            onDismissRequest = { pendingAction = null },
            title = { Text("Подтвердите изменение Wi-Fi") },
            text = { Text("Перед применением агент создаст backup конфигурации wireless.") },
            confirmButton = {
                TextButton(onClick = {
                    pendingAction = null
                    action()
                }) { Text("Применить") }
            },
            dismissButton = {
                TextButton(onClick = { pendingAction = null }) { Text(stringResource(R.string.cancel)) }
            },
        )
    }
}

@Composable
fun NetworkControlScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var message by remember { mutableStateOf("") }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> telemetry = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
            }
        }
        Unit
    }
    LaunchedEffect(device.id) { refresh() }
    val interfaces = telemetry?.network?.optJSONArray("interfaces")
        ?: telemetry?.payload?.optJSONObject("network")?.optJSONArray("interfaces")
        ?: telemetry?.payload?.optJSONObject("network")?.optJSONArray("interface")
    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()

    Text(stringResource(R.string.network), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (interfaces == null || interfaces.length() == 0) {
                Text("Данные интерфейсов еще не получены")
            } else {
                for (index in 0 until interfaces.length()) {
                    val item = interfaces.optJSONObject(index)
                    val title = item?.optString("interface", item.optString("name", "interface")) ?: "interface"
                    val details = listOfNotNull(
                        if (item?.optBoolean("up", false) == true) "В сети" else "Не в сети",
                        item?.optString("proto").takeUnless { it.isNullOrBlank() },
                        item?.optString("device").takeUnless { it.isNullOrBlank() },
                        item?.optJSONArray("ipv4")?.optString(0).takeUnless { it.isNullOrBlank() },
                    ).joinToString(" · ")
                    InfoRow(title, details)
                }
            }
            if (capabilities["network.read"] == true) {
                Button(
                    onClick = {
                        scope.launch {
                            when (val result = withContext(Dispatchers.IO) {
                                WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, "network.interfaces", JSONObject(), confirmed = true)
                            }) {
                                is ApiResult.Success -> {
                                    message = "Запрос интерфейсов добавлен"
                                    refresh()
                                }
                                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Запросить интерфейсы") }
            }
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.primary)
            TextButton(onClick = refresh, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refresh)) }
        }
    }
}

@Composable
fun SystemControlScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var commands by remember { mutableStateOf<List<CommandDto>>(emptyList()) }
    var message by remember { mutableStateOf("") }
    var confirmReboot by remember { mutableStateOf(false) }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> telemetry = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
            }
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getCommands(device.id) }) {
                is ApiResult.Success -> commands = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
            }
        }
        Unit
    }
    LaunchedEffect(device.id) { refresh() }
    val system = telemetry?.payload?.optJSONObject("system")
    val memory = system?.optJSONObject("memory")
    val storage = telemetry?.payload?.optJSONObject("storage")
    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()
    val latestDiagnostics = commands.firstOrNull { it.commandType == "diagnostics.run" }

    Text(stringResource(R.string.system), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            InfoRow(stringResource(R.string.router), device.name.ifBlank { device.hostname })
            InfoRow(stringResource(R.string.uptime), formatDuration(system?.optLong("uptime", 0) ?: 0))
            InfoRow(stringResource(R.string.load), system?.optString("load"))
            InfoRow(stringResource(R.string.memory), memory?.let { "${it.optLong("available_kb") / 1024} / ${it.optLong("total_kb") / 1024} MB" })
            InfoRow("Накопитель", storage?.let { "${it.optLong("used_kb") / 1024} / ${it.optLong("total_kb") / 1024} MB" })

            if (capabilities["system.reboot"] == true) {
                Button(onClick = { confirmReboot = true }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.reboot)) }
            }
            if (capabilities["diagnostics.check_server"] == true) {
                Button(
                    onClick = {
                        scope.launch {
                            when (val result = withContext(Dispatchers.IO) {
                                WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, "diagnostics.run", JSONObject(), confirmed = true)
                            }) {
                                is ApiResult.Success -> {
                                    message = "Команда диагностики добавлена"
                                    refresh()
                                }
                                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Диагностика") }
            }

            latestDiagnostics?.let {
                InfoRow("Последняя диагностика", it.status)
                it.result?.let { json -> Text(json.toString(2), style = MaterialTheme.typography.bodySmall) }
            }
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.primary)
            TextButton(onClick = refresh, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refresh)) }
        }
    }
    if (confirmReboot) AlertDialog(
        onDismissRequest = { confirmReboot = false },
        title = { Text(stringResource(R.string.reboot_confirm_title)) },
        text = { Text(stringResource(R.string.reboot_confirm_message)) },
        confirmButton = {
            TextButton(
                onClick = {
                    confirmReboot = false
                    scope.launch {
                        when (val result = withContext(Dispatchers.IO) {
                            WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, "router.reboot", JSONObject(), confirmed = true)
                        }) {
                            is ApiResult.Success -> message = "Команда перезагрузки добавлена"
                            is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
                        }
                    }
                },
            ) { Text(stringResource(R.string.reboot)) }
        },
        dismissButton = { TextButton(onClick = { confirmReboot = false }) { Text(stringResource(R.string.cancel)) } },
    )
}

private fun firstRadio(telemetry: TelemetryDto?): JSONObject? =
    telemetry?.wifi?.optJSONArray("radios")?.optJSONObject(0)
        ?: telemetry?.payload?.optJSONObject("wifi")?.optJSONArray("radios")?.optJSONObject(0)

private fun firstInterface(telemetry: TelemetryDto?): JSONObject? =
    firstRadio(telemetry)?.optJSONArray("interfaces")?.optJSONObject(0)

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
