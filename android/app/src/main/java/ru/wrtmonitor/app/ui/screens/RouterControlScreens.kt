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
fun ClientsControlScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var hostname by remember { mutableStateOf("") }
    var mac by remember { mutableStateOf("") }
    var ip by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var pendingCommand by remember { mutableStateOf<Pair<String, JSONObject>?>(null) }

    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> telemetry = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
            }
        }
    }
    fun queue(type: String, payload: JSONObject) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, type, payload, true) }) {
                is ApiResult.Success -> {
                    message = "queued"
                    if (type == "dhcp.set_lease") {
                        hostname = ""
                        mac = ""
                        ip = ""
                    }
                    refresh()
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
            }
        }
    }

    LaunchedEffect(device.id) { refresh() }
    val clients = telemetry?.clients?.optJSONArray("items") ?: JSONArray()
    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()
    val queuedText = stringResource(R.string.lease_queued)

    Text(stringResource(R.string.clients), style = MaterialTheme.typography.titleLarge)
    Text(stringResource(R.string.clients_found, clients.length()), color = MaterialTheme.colorScheme.onSurfaceVariant)
    if (clients.length() == 0) {
        Card(Modifier.fillMaxWidth()) { Text(stringResource(R.string.no_data), Modifier.padding(16.dp)) }
    }
    for (index in 0 until clients.length()) {
        val client = clients.optJSONObject(index) ?: continue
        val clientMac = client.optString("mac")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(client.optString("hostname").ifBlank { stringResource(R.string.client_unknown) }, style = MaterialTheme.typography.titleMedium)
                InfoRow(stringResource(R.string.ip_address), client.optString("ip"), stringResource(R.string.no_data))
                InfoRow(stringResource(R.string.mac_address), clientMac, stringResource(R.string.no_data))
                InfoRow(stringResource(R.string.status), client.optString("state"), stringResource(R.string.no_data))
                InfoRow(stringResource(R.string.client_source), client.optString("source"), stringResource(R.string.no_data))
                if (capabilities["dhcp.delete_lease"] == true && client.optBoolean("is_static", false)) {
                    TextButton(
                        onClick = { pendingCommand = "dhcp.delete_lease" to JSONObject().put("mac", clientMac) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(stringResource(R.string.delete_lease)) }
                }
            }
        }
    }

    if (capabilities["dhcp.set_lease"] == true) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(stringResource(R.string.static_lease), style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(hostname, { hostname = it }, label = { Text(stringResource(R.string.device_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(mac, { mac = it }, label = { Text(stringResource(R.string.mac_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(ip, { ip = it }, label = { Text(stringResource(R.string.ip_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(
                    onClick = { pendingCommand = "dhcp.set_lease" to JSONObject().put("hostname", hostname).put("mac", mac).put("ip", ip) },
                    enabled = hostname.isNotBlank() && mac.length >= 17 && ip.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.save_lease)) }
            }
        }
    }
    if (message == "queued") Text(queuedText, color = MaterialTheme.colorScheme.primary)
    else if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.error)
    TextButton(onClick = refresh, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refresh)) }

    pendingCommand?.let { command ->
        AlertDialog(
            onDismissRequest = { pendingCommand = null },
            title = { Text(stringResource(R.string.confirm_action)) },
            text = { Text(stringResource(R.string.config_backup_notice)) },
            confirmButton = { TextButton(onClick = { pendingCommand = null; queue(command.first, command.second) }) { Text(stringResource(R.string.apply)) } },
            dismissButton = { TextButton(onClick = { pendingCommand = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

@Composable
fun WifiControlScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var ssid by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var enabled by remember { mutableStateOf(true) }
    var channel by remember { mutableStateOf("") }
    var country by remember { mutableStateOf("") }
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
                    channel = radio?.optString("channel").orEmpty()
                    country = radio?.optString("country").orEmpty()
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
    val wifiSsidQueued = stringResource(R.string.wifi_ssid_queued)
    val wifiPasswordQueued = stringResource(R.string.wifi_password_queued)
    val wifiToggleQueued = stringResource(R.string.wifi_toggle_queued)
    val wifiChannelQueued = stringResource(R.string.wifi_channel_queued)
    val wifiCountryQueued = stringResource(R.string.wifi_country_queued)

    Text(stringResource(R.string.wifi), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            InfoRow(stringResource(R.string.wifi_status), if (wifi?.optBoolean("available", false) == true) stringResource(R.string.available) else stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.wifi_radios), wifi?.optJSONArray("radios")?.length()?.toString(), stringResource(R.string.no_data))
            iface?.let { InfoRow(stringResource(R.string.current_ssid), it.optString("ssid").ifBlank { stringResource(R.string.no_data) }, stringResource(R.string.no_data)) }

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
                            queue("wifi.set_ssid", JSONObject().put("ssid", ssid).put("iface", ifaceId), wifiSsidQueued)
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = ssid.isNotBlank(),
                ) { Text(stringResource(R.string.apply_ssid)) }
            }

            if (capabilities["wifi.set_password"] == true) {
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text(stringResource(R.string.new_wifi_password)) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                )
                Button(
                    onClick = {
                        pendingAction = {
                            queue("wifi.set_password", JSONObject().put("password", password).put("iface", ifaceId), wifiPasswordQueued)
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = password.length >= 8,
                ) { Text(stringResource(R.string.change_password)) }
            }

            if (capabilities["wifi.enable"] == true || capabilities["wifi.disable"] == true) {
                InfoRow(stringResource(R.string.wifi_state), if (enabled) stringResource(R.string.wifi_enabled_state) else stringResource(R.string.wifi_disabled_state), stringResource(R.string.no_data))
                Switch(checked = enabled, onCheckedChange = { enabled = it })
                Button(
                    onClick = {
                        pendingAction = {
                            queue("wifi.set_enabled", JSONObject().put("enabled", enabled).put("radio", radioId), wifiToggleQueued)
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.wifi_state_apply)) }
            }

            if (capabilities["wifi.set_channel"] == true) {
                OutlinedTextField(channel, { channel = it }, label = { Text(stringResource(R.string.wifi_channel)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(
                    onClick = { pendingAction = { queue("wifi.set_channel", JSONObject().put("channel", channel).put("radio", radioId), wifiChannelQueued) } },
                    enabled = channel.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.change_channel)) }
            }
            if (capabilities["wifi.set_country"] == true) {
                OutlinedTextField(country, { country = it.uppercase().take(2) }, label = { Text(stringResource(R.string.wifi_country)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(
                    onClick = { pendingAction = { queue("wifi.set_country", JSONObject().put("country", country).put("radio", radioId), wifiCountryQueued) } },
                    enabled = country.length == 2,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.change_country)) }
            }

            if (capabilities.isEmpty()) {
                Text(
                    stringResource(R.string.capabilities_missing_reinstall),
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.primary)
            TextButton(onClick = refresh, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refresh)) }
        }
    }

    pendingAction?.let { action ->
        AlertDialog(
            onDismissRequest = { pendingAction = null },
            title = { Text(stringResource(R.string.wifi_confirm_title)) },
            text = { Text(stringResource(R.string.wifi_confirm_message)) },
            confirmButton = {
                TextButton(onClick = {
                    pendingAction = null
                    action()
                }) { Text(stringResource(R.string.apply)) }
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
    var interfaceName by remember { mutableStateOf("wan") }
    var pendingCommand by remember { mutableStateOf<Pair<String, JSONObject>?>(null) }
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
    val interfacesRequestQueued = stringResource(R.string.interfaces_request_queued)
    val interfaceRestartQueued = stringResource(R.string.interface_restart_queued)
    val networkRestartQueued = stringResource(R.string.network_restart_queued)

    fun queue(type: String, payload: JSONObject, success: String) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, type, payload, true) }) {
                is ApiResult.Success -> { message = success; refresh() }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
            }
        }
    }

    Text(stringResource(R.string.network), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (interfaces == null || interfaces.length() == 0) {
                Text(stringResource(R.string.network_pending))
            } else {
                for (index in 0 until interfaces.length()) {
                    val item = interfaces.optJSONObject(index)
                    val title = item?.optString("interface", item.optString("name", "interface")) ?: "interface"
                    val details = listOfNotNull(
                        if (item?.optBoolean("up", false) == true) stringResource(R.string.in_network) else stringResource(R.string.out_of_network),
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
                                    message = interfacesRequestQueued
                                    refresh()
                                }
                                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.request_interfaces)) }
            }
            if (capabilities["network.interface_restart"] == true) {
                OutlinedTextField(
                    value = interfaceName,
                    onValueChange = { interfaceName = it },
                    label = { Text(stringResource(R.string.network_interfaces)) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
                Button(
                    onClick = { pendingCommand = "network.interface_restart" to JSONObject().put("interface", interfaceName) },
                    enabled = interfaceName.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.restart_interface)) }
            }
            if (capabilities["network.restart"] == true) {
                Button(
                    onClick = { pendingCommand = "network.restart" to JSONObject() },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.restart_network)) }
            }
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.primary)
            TextButton(onClick = refresh, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.refresh)) }
        }
    }
    pendingCommand?.let { command ->
        AlertDialog(
            onDismissRequest = { pendingCommand = null },
            title = { Text(stringResource(R.string.confirm_action)) },
            text = { Text(stringResource(R.string.network_restart_warning)) },
            confirmButton = {
                TextButton(onClick = {
                    pendingCommand = null
                    queue(command.first, command.second, if (command.first == "network.restart") networkRestartQueued else interfaceRestartQueued)
                }) { Text(stringResource(R.string.apply)) }
            },
            dismissButton = { TextButton(onClick = { pendingCommand = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

@Composable
fun SystemControlScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var commands by remember { mutableStateOf<List<CommandDto>>(emptyList()) }
    var message by remember { mutableStateOf("") }
    var confirmReboot by remember { mutableStateOf(false) }
    var hostnameValue by remember { mutableStateOf("") }
    var pendingSystemCommand by remember { mutableStateOf<Pair<String, JSONObject>?>(null) }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    hostnameValue = result.data.system?.optString("hostname").orEmpty().ifBlank { device.hostname }
                }
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
    val systemSummary = telemetry?.system
    val services = telemetry?.services
    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()
    val latestDiagnostics = commands.firstOrNull { it.commandType == "diagnostics.run" }
    val diagnosticsQueued = stringResource(R.string.diagnostics_queued)
    val rebootQueued = stringResource(R.string.reboot_queued)
    val hostnameQueued = stringResource(R.string.hostname_queued)
    val serviceQueued = stringResource(R.string.service_restart_queued)

    fun queueSystem(type: String, payload: JSONObject, success: String) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, type, payload, true) }) {
                is ApiResult.Success -> { message = success; refresh() }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
            }
        }
    }

    Text(stringResource(R.string.system), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            InfoRow(stringResource(R.string.router), device.name.ifBlank { device.hostname })
            InfoRow(stringResource(R.string.uptime), formatDuration(system?.optLong("uptime", 0) ?: 0))
            InfoRow(stringResource(R.string.load), system?.optString("load"))
            InfoRow(stringResource(R.string.memory), memory?.let { "${it.optLong("available_kb") / 1024} / ${it.optLong("total_kb") / 1024} MB" })
            InfoRow(stringResource(R.string.storage), storage?.let { "${it.optLong("used_kb") / 1024} / ${it.optLong("total_kb") / 1024} MB" }, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.kernel), systemSummary?.optString("kernel"), stringResource(R.string.no_data))
            InfoRow(
                stringResource(R.string.connections),
                systemSummary?.let { "${it.optLong("conntrack_count")} / ${it.optLong("conntrack_max")}" },
                stringResource(R.string.no_data),
            )

            if (services != null) {
                Text(stringResource(R.string.services), style = MaterialTheme.typography.titleMedium)
                listOf("network", "dnsmasq", "firewall", "odhcpd").forEach { service ->
                    InfoRow(service, services.optString(service), stringResource(R.string.no_data))
                }
            }

            if (capabilities["system.set_hostname"] == true) {
                OutlinedTextField(hostnameValue, { hostnameValue = it }, label = { Text(stringResource(R.string.new_hostname)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(
                    onClick = { pendingSystemCommand = "system.set_hostname" to JSONObject().put("hostname", hostnameValue) },
                    enabled = hostnameValue.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.change_hostname)) }
            }
            if (capabilities["system.restart_service"] == true) {
                listOf("dnsmasq", "firewall", "odhcpd", "network").forEach { service ->
                    TextButton(
                        onClick = { pendingSystemCommand = "system.restart_service" to JSONObject().put("service", service) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("${stringResource(R.string.restart_service)}: $service") }
                }
            }

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
                                    message = diagnosticsQueued
                                    refresh()
                                }
                                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.diagnostics)) }
            }

            latestDiagnostics?.let {
                InfoRow(stringResource(R.string.last_diagnostics), it.status, stringResource(R.string.no_data))
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
                            is ApiResult.Success -> message = rebootQueued
                            is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else message = result.message
                        }
                    }
                },
            ) { Text(stringResource(R.string.reboot)) }
        },
        dismissButton = { TextButton(onClick = { confirmReboot = false }) { Text(stringResource(R.string.cancel)) } },
    )
    pendingSystemCommand?.let { command ->
        AlertDialog(
            onDismissRequest = { pendingSystemCommand = null },
            title = { Text(stringResource(R.string.confirm_action)) },
            text = { Text(stringResource(R.string.config_backup_notice)) },
            confirmButton = {
                TextButton(onClick = {
                    pendingSystemCommand = null
                    queueSystem(command.first, command.second, if (command.first == "system.set_hostname") hostnameQueued else serviceQueued)
                }) { Text(stringResource(R.string.apply)) }
            },
            dismissButton = { TextButton(onClick = { pendingSystemCommand = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
}

private fun firstRadio(telemetry: TelemetryDto?): JSONObject? =
    telemetry?.wifi?.optJSONArray("radios")?.optJSONObject(0)
        ?: telemetry?.payload?.optJSONObject("wifi")?.optJSONArray("radios")?.optJSONObject(0)

private fun firstInterface(telemetry: TelemetryDto?): JSONObject? =
    firstRadio(telemetry)?.optJSONArray("interfaces")?.optJSONObject(0)

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
