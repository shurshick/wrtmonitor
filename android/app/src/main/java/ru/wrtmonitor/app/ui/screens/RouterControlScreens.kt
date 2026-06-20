package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.ui.components.InfoRow

@Composable
fun WifiControlScreen(serverUrl: String, accessToken: String, device: DeviceDto) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var ssid by remember { mutableStateOf("") }
    var enabled by remember { mutableStateOf(true) }
    var message by remember { mutableStateOf("") }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    val wifi = result.data.payload?.optJSONObject("wifi")
                    val radios = wifi?.optJSONArray("radios")
                    val first = radios?.optJSONObject(0)
                    ssid = first?.optJSONArray("ssid")?.optString(0).orEmpty()
                    enabled = first?.optBoolean("up", true) ?: true
                }
                is ApiResult.Error -> message = result.message
            }
        }
        Unit
    }
    LaunchedEffect(device.id) { refresh() }
    val wifi = telemetry?.payload?.optJSONObject("wifi")
    val radios = wifi?.optJSONArray("radios")
    Text(stringResource(R.string.wifi), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            InfoRow("Статус", if (wifi?.optBoolean("available", false) == true) "Доступно" else "Нет данных")
            InfoRow("Радиомодули", radios?.length()?.toString())
            OutlinedTextField(ssid, { ssid = it }, label = { Text("SSID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Wi-Fi")
                Switch(checked = enabled, onCheckedChange = { enabled = it })
            }
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.error)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, "wifi.set_ssid", JSONObject().put("ssid", ssid))
                        }
                        message = if (result is ApiResult.Success) "Команда изменения SSID добавлена" else (result as ApiResult.Error).message
                    }
                }) { Text("Применить SSID") }
                Button(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, "wifi.set_enabled", JSONObject().put("enabled", enabled))
                        }
                        message = if (result is ApiResult.Success) "Команда Wi-Fi добавлена" else (result as ApiResult.Error).message
                    }
                }) { Text("Применить Wi-Fi") }
            }
            TextButton(onClick = refresh) { Text(stringResource(R.string.refresh)) }
        }
    }
}

@Composable
fun NetworkControlScreen(serverUrl: String, accessToken: String, device: DeviceDto) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var message by remember { mutableStateOf("") }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> telemetry = result.data
                is ApiResult.Error -> message = result.message
            }
        }
        Unit
    }
    LaunchedEffect(device.id) { refresh() }
    val network = telemetry?.payload?.optJSONObject("network")
    val interfaces = network?.optJSONArray("interfaces") ?: network?.optJSONArray("interface")
    Text(stringResource(R.string.network), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (interfaces == null || interfaces.length() == 0) {
                Text("Данные интерфейсов ещё не получены")
            } else {
                for (index in 0 until interfaces.length()) {
                    val item = interfaces.optJSONObject(index)
                    InfoRow(item?.optString("interface", item.optString("name", "interface")) ?: "interface", if (item?.optBoolean("up", false) == true) "В сети" else "Не в сети")
                }
            }
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.error)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, "network.interfaces", JSONObject())
                        }
                        message = if (result is ApiResult.Success) "Запрос интерфейсов добавлен" else (result as ApiResult.Error).message
                    }
                }) { Text("Запросить интерфейсы") }
                TextButton(onClick = refresh) { Text(stringResource(R.string.refresh)) }
            }
        }
    }
}

@Composable
fun SystemControlScreen(serverUrl: String, accessToken: String, device: DeviceDto) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var message by remember { mutableStateOf("") }
    var confirmReboot by remember { mutableStateOf(false) }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> telemetry = result.data
                is ApiResult.Error -> message = result.message
            }
        }
        Unit
    }
    LaunchedEffect(device.id) { refresh() }
    val system = telemetry?.payload?.optJSONObject("system")
    Text(stringResource(R.string.system), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            InfoRow(stringResource(R.string.router), device.name.ifBlank { device.hostname })
            InfoRow(stringResource(R.string.uptime), system?.optLong("uptime", 0)?.toString())
            InfoRow(stringResource(R.string.load), system?.optString("load"))
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.primary)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { confirmReboot = true }) { Text(stringResource(R.string.reboot)) }
                TextButton(onClick = refresh) { Text(stringResource(R.string.refresh)) }
            }
        }
    }
    if (confirmReboot) {
        AlertDialog(
            onDismissRequest = { confirmReboot = false },
            title = { Text(stringResource(R.string.reboot_confirm_title)) },
            text = { Text(stringResource(R.string.reboot_confirm_message)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmReboot = false
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, "router.reboot", JSONObject())
                        }
                        message = if (result is ApiResult.Success) "Команда перезагрузки добавлена" else (result as ApiResult.Error).message
                    }
                }) { Text(stringResource(R.string.reboot)) }
            },
            dismissButton = { TextButton(onClick = { confirmReboot = false }) { Text(stringResource(R.string.cancel)) } }
        )
    }
}
