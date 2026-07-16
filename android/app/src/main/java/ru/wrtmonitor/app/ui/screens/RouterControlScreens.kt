package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.Alignment
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
import ru.wrtmonitor.app.ui.components.ActionRow
import ru.wrtmonitor.app.ui.components.ExpandableSettingsCard
import ru.wrtmonitor.app.ui.components.MessageBanner
import ru.wrtmonitor.app.ui.components.MetricTile
import ru.wrtmonitor.app.ui.components.RouterPageHeader
import ru.wrtmonitor.app.ui.components.SectionCard
import ru.wrtmonitor.app.ui.components.StatusPill
import ru.wrtmonitor.app.ui.components.SwitchSettingRow

@Composable
fun ClientsControlScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var hostname by remember { mutableStateOf("") }
    var mac by remember { mutableStateOf("") }
    var ip by remember { mutableStateOf("") }
    var poolStart by remember { mutableStateOf("100") }
    var poolLimit by remember { mutableStateOf("150") }
    var leaseTime by remember { mutableStateOf("12h") }
    var message by remember { mutableStateOf("") }
    var messageIsError by remember { mutableStateOf(false) }
    var pendingCommand by remember { mutableStateOf<Pair<String, JSONObject>?>(null) }
    val leaseQueuedText = stringResource(R.string.lease_queued)
    val genericQueuedText = stringResource(R.string.command_queued)

    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> telemetry = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
        }
    }
    fun queue(type: String, payload: JSONObject) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, type, payload, true) }) {
                is ApiResult.Success -> {
                    message = if (type.startsWith("dhcp.")) leaseQueuedText else genericQueuedText
                    messageIsError = false
                    if (type == "dhcp.set_lease") {
                        hostname = ""
                        mac = ""
                        ip = ""
                    }
                    refresh()
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
        }
    }

    LaunchedEffect(device.id) { refresh() }
    val clients = telemetry?.clients?.optJSONArray("items") ?: JSONArray()
    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()

    RouterPageHeader(
        title = stringResource(R.string.home_network),
        subtitle = stringResource(R.string.clients_found, clients.length()),
        onRefresh = refresh,
    )
    if (clients.length() == 0) {
        Card(Modifier.fillMaxWidth()) { Text(stringResource(R.string.no_data), Modifier.padding(16.dp)) }
    }
    for (index in 0 until clients.length()) {
        val client = clients.optJSONObject(index) ?: continue
        val clientMac = client.optString("mac")
        val clientState = client.optString("state")
        val clientOnline = clientState.lowercase() !in setOf("", "offline", "expired", "failed")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        client.optString("hostname").ifBlank { stringResource(R.string.client_unknown) },
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.weight(1f),
                    )
                    StatusPill(
                        if (clientOnline) stringResource(R.string.online) else stringResource(R.string.offline),
                        clientOnline,
                    )
                }
                InfoRow(stringResource(R.string.ip_address), client.optString("ip"), stringResource(R.string.no_data))
                InfoRow(stringResource(R.string.mac_address), clientMac, stringResource(R.string.no_data))
                InfoRow(stringResource(R.string.client_source), client.optString("source"), stringResource(R.string.no_data))
                if (capabilities["dhcp.delete_lease"] == true && client.optBoolean("is_static", false)) {
                    TextButton(
                        onClick = { pendingCommand = "dhcp.delete_lease" to JSONObject().put("mac", clientMac) },
                        modifier = Modifier.align(Alignment.End),
                    ) { Text(stringResource(R.string.delete_lease)) }
                }
                if (capabilities["clients.block"] == true && clientMac.isNotBlank()) {
                    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.End) {
                        TextButton(
                            onClick = { pendingCommand = "client.set_blocked" to JSONObject().put("mac", clientMac).put("blocked", true) },
                        ) { Text(stringResource(R.string.block_client)) }
                        TextButton(
                            onClick = { pendingCommand = "client.set_blocked" to JSONObject().put("mac", clientMac).put("blocked", false) },
                        ) { Text(stringResource(R.string.unblock_client)) }
                    }
                }
            }
        }
    }

    if (capabilities["dhcp.set_lease"] == true) {
        ExpandableSettingsCard(
            title = stringResource(R.string.static_lease),
            summary = stringResource(R.string.static_lease_summary),
        ) {
            OutlinedTextField(hostname, { hostname = it }, label = { Text(stringResource(R.string.device_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(mac, { mac = it }, label = { Text(stringResource(R.string.mac_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ip, { ip = it }, label = { Text(stringResource(R.string.ip_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Button(
                onClick = { pendingCommand = "dhcp.set_lease" to JSONObject().put("hostname", hostname).put("mac", mac).put("ip", ip) },
                enabled = hostname.isNotBlank() && mac.length >= 17 && ip.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            ) { Text(stringResource(R.string.save_lease)) }
        }
    }
    if (capabilities["dhcp.configure"] == true) {
        ExpandableSettingsCard(
            title = stringResource(R.string.dhcp_pool),
            summary = "$poolStart · $poolLimit · $leaseTime",
        ) {
            OutlinedTextField(poolStart, { poolStart = it }, label = { Text(stringResource(R.string.pool_start)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(poolLimit, { poolLimit = it }, label = { Text(stringResource(R.string.pool_size)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(leaseTime, { leaseTime = it }, label = { Text(stringResource(R.string.lease_time)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Button(
                onClick = { pendingCommand = "dhcp.set_pool" to JSONObject().put("interface", "lan").put("start", poolStart).put("limit", poolLimit).put("leasetime", leaseTime) },
                modifier = Modifier.align(Alignment.End),
            ) { Text(stringResource(R.string.save_dhcp)) }
        }
    }
    MessageBanner(message, error = messageIsError)

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
    var guestSsid by remember { mutableStateOf("Guest Wi-Fi") }
    var guestPassword by remember { mutableStateOf("") }
    var guestEnabled by remember { mutableStateOf(true) }
    var message by remember { mutableStateOf("") }
    var messageIsError by remember { mutableStateOf(false) }
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
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
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
                    messageIsError = false
                    if (type == "wifi.set_password") password = ""
                    refresh()
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
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

    val radios = wifi?.optJSONArray("radios") ?: JSONArray()
    RouterPageHeader(
        title = stringResource(R.string.wifi),
        subtitle = stringResource(R.string.wifi_screen_summary),
        onRefresh = refresh,
    )
    SectionCard(
        title = stringResource(R.string.wifi_status),
        subtitle = stringResource(R.string.radio_count_value, radios.length()),
    ) {
        if (wifi?.optBoolean("available", false) != true || radios.length() == 0) {
            Text(stringResource(R.string.wifi_unavailable), color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            for (index in 0 until radios.length()) {
                val item = radios.optJSONObject(index) ?: continue
                val radioName = item.optString("id").ifBlank { "radio$index" }
                val details = listOfNotNull(
                    item.optString("band").takeIf(String::isNotBlank),
                    item.optString("channel").takeIf(String::isNotBlank)?.let { stringResource(R.string.channel_value, it) },
                    item.optString("country").takeIf(String::isNotBlank),
                ).joinToString(" · ")
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(radioName, style = MaterialTheme.typography.titleSmall)
                        Text(details, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    StatusPill(
                        if (item.optBoolean("up", false)) stringResource(R.string.enabled_value) else stringResource(R.string.disabled_value),
                        item.optBoolean("up", false),
                    )
                }
                if (index < radios.length() - 1) HorizontalDivider()
            }
        }
    }

    if (capabilities["wifi.set_ssid"] == true || capabilities["wifi.set_password"] == true || capabilities["wifi.enable"] == true || capabilities["wifi.disable"] == true) {
        SectionCard(
            title = stringResource(R.string.main_wifi_network),
            subtitle = iface?.optString("ssid").orEmpty().ifBlank { stringResource(R.string.no_data) },
        ) {
            if (capabilities["wifi.enable"] == true || capabilities["wifi.disable"] == true) {
                SwitchSettingRow(
                    title = stringResource(R.string.wifi_state),
                    subtitle = if (enabled) stringResource(R.string.wifi_enabled_state) else stringResource(R.string.wifi_disabled_state),
                    checked = enabled,
                    onCheckedChange = { enabled = it },
                )
                OutlinedButton(
                    onClick = { pendingAction = { queue("wifi.set_enabled", JSONObject().put("enabled", enabled).put("radio", radioId), wifiToggleQueued) } },
                    modifier = Modifier.align(Alignment.End),
                ) { Text(stringResource(R.string.wifi_state_apply)) }
            }
            if (capabilities["wifi.set_ssid"] == true) {
                HorizontalDivider()
                OutlinedTextField(ssid, { ssid = it }, label = { Text("SSID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(
                    onClick = { pendingAction = { queue("wifi.set_ssid", JSONObject().put("ssid", ssid).put("iface", ifaceId), wifiSsidQueued) } },
                    modifier = Modifier.align(Alignment.End),
                    enabled = ssid.isNotBlank(),
                ) { Text(stringResource(R.string.apply_ssid)) }
            }
            if (capabilities["wifi.set_password"] == true) {
                HorizontalDivider()
                OutlinedTextField(password, { password = it }, label = { Text(stringResource(R.string.new_wifi_password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
                Button(
                    onClick = { pendingAction = { queue("wifi.set_password", JSONObject().put("password", password).put("iface", ifaceId), wifiPasswordQueued) } },
                    modifier = Modifier.align(Alignment.End),
                    enabled = password.length >= 8,
                ) { Text(stringResource(R.string.change_password)) }
            }
        }
    }

    if (capabilities["wifi.set_channel"] == true || capabilities["wifi.set_country"] == true) {
        ExpandableSettingsCard(
            title = stringResource(R.string.wifi_radio_settings),
            summary = listOf(channel, country).filter(String::isNotBlank).joinToString(" · "),
        ) {
            if (capabilities["wifi.set_channel"] == true) {
                OutlinedTextField(channel, { channel = it }, label = { Text(stringResource(R.string.wifi_channel)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(
                    onClick = { pendingAction = { queue("wifi.set_channel", JSONObject().put("channel", channel).put("radio", radioId), wifiChannelQueued) } },
                    enabled = channel.isNotBlank(),
                    modifier = Modifier.align(Alignment.End),
                ) { Text(stringResource(R.string.change_channel)) }
            }
            if (capabilities["wifi.set_country"] == true) {
                OutlinedTextField(country, { country = it.uppercase().take(2) }, label = { Text(stringResource(R.string.wifi_country)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(
                    onClick = { pendingAction = { queue("wifi.set_country", JSONObject().put("country", country).put("radio", radioId), wifiCountryQueued) } },
                    enabled = country.length == 2,
                    modifier = Modifier.align(Alignment.End),
                ) { Text(stringResource(R.string.change_country)) }
            }
        }
    }
    if (capabilities["wifi.guest"] == true) {
        ExpandableSettingsCard(
            title = stringResource(R.string.guest_wifi),
            summary = guestSsid,
        ) {
            SwitchSettingRow(stringResource(R.string.wifi_state), checked = guestEnabled, onCheckedChange = { guestEnabled = it })
            OutlinedTextField(guestSsid, { guestSsid = it }, label = { Text("SSID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(guestPassword, { guestPassword = it }, label = { Text(stringResource(R.string.wifi_password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
            Button(
                onClick = { pendingAction = { queue("wifi.set_guest", JSONObject().put("enabled", guestEnabled).put("ssid", guestSsid).put("password", guestPassword).put("radio", radioId), wifiToggleQueued) } },
                enabled = !guestEnabled || (guestSsid.isNotBlank() && guestPassword.length >= 8),
                modifier = Modifier.align(Alignment.End),
            ) { Text(stringResource(R.string.apply_guest_wifi)) }
        }
    }

    if (capabilities.isEmpty()) MessageBanner(stringResource(R.string.capabilities_missing_reinstall))
    MessageBanner(message, error = messageIsError)

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
    var messageIsError by remember { mutableStateOf(false) }
    var interfaceName by remember { mutableStateOf("wan") }
    var wanProtocol by remember { mutableStateOf("dhcp") }
    var wanIp by remember { mutableStateOf("") }
    var wanNetmask by remember { mutableStateOf("") }
    var wanGateway by remember { mutableStateOf("") }
    var wanDns by remember { mutableStateOf("") }
    var wanUsername by remember { mutableStateOf("") }
    var wanPassword by remember { mutableStateOf("") }
    var lanIp by remember { mutableStateOf("192.168.1.1") }
    var lanNetmask by remember { mutableStateOf("255.255.255.0") }
    var dnsServers by remember { mutableStateOf("1.1.1.1, 8.8.8.8") }
    var forwardName by remember { mutableStateOf("") }
    var forwardExternalPort by remember { mutableStateOf("") }
    var forwardInternalIp by remember { mutableStateOf("") }
    var forwardInternalPort by remember { mutableStateOf("") }
    var pendingCommand by remember { mutableStateOf<Pair<String, JSONObject>?>(null) }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> telemetry = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
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
    val genericCommandQueued = stringResource(R.string.command_queued)

    fun queue(type: String, payload: JSONObject, success: String) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, type, payload, true) }) {
                is ApiResult.Success -> { message = success; messageIsError = false; refresh() }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
        }
    }

    RouterPageHeader(
        title = stringResource(R.string.internet),
        subtitle = stringResource(R.string.internet_screen_summary),
        onRefresh = refresh,
    )
    SectionCard(
        title = stringResource(R.string.network_interfaces),
        subtitle = stringResource(R.string.interfaces_count, interfaces?.length() ?: 0),
    ) {
        if (interfaces == null || interfaces.length() == 0) {
            Text(stringResource(R.string.network_pending), color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            for (index in 0 until interfaces.length()) {
                val item = interfaces.optJSONObject(index)
                val title = item?.optString("interface", item.optString("name", "interface")) ?: "interface"
                val isUp = item?.optBoolean("up", false) == true
                val details = listOfNotNull(
                    item?.optString("proto").takeUnless { it.isNullOrBlank() },
                    item?.optString("device").takeUnless { it.isNullOrBlank() },
                    item?.optJSONArray("ipv4")?.optString(0).takeUnless { it.isNullOrBlank() },
                ).joinToString(" · ")
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(title, style = MaterialTheme.typography.titleSmall)
                        Text(details.ifBlank { stringResource(R.string.no_data) }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    StatusPill(if (isUp) stringResource(R.string.in_network) else stringResource(R.string.out_of_network), isUp)
                }
                if (index < interfaces.length() - 1) HorizontalDivider()
            }
        }
        if (capabilities["network.read"] == true) {
            OutlinedButton(
                onClick = {
                    scope.launch {
                        when (val result = withContext(Dispatchers.IO) {
                            WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, "network.interfaces", JSONObject(), confirmed = true)
                        }) {
                            is ApiResult.Success -> { message = interfacesRequestQueued; messageIsError = false; refresh() }
                            is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                                message = result.message
                                messageIsError = true
                            }
                        }
                    }
                },
                modifier = Modifier.align(Alignment.End),
            ) { Text(stringResource(R.string.request_interfaces)) }
        }
    }

    if (capabilities["network.wan.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.wan_settings), wanProtocol.uppercase()) {
            OutlinedTextField(wanProtocol, { wanProtocol = it.lowercase() }, label = { Text(stringResource(R.string.connection_type)) }, supportingText = { Text("dhcp / static / pppoe") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            if (wanProtocol == "static") {
                OutlinedTextField(wanIp, { wanIp = it }, label = { Text(stringResource(R.string.ip_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(wanNetmask, { wanNetmask = it }, label = { Text(stringResource(R.string.netmask)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(wanGateway, { wanGateway = it }, label = { Text(stringResource(R.string.gateway)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            }
            if (wanProtocol == "pppoe") {
                OutlinedTextField(wanUsername, { wanUsername = it }, label = { Text(stringResource(R.string.username)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(wanPassword, { wanPassword = it }, label = { Text(stringResource(R.string.password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
            }
            OutlinedTextField(wanDns, { wanDns = it }, label = { Text(stringResource(R.string.dns_servers)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Button(
                onClick = { pendingCommand = "network.set_wan" to JSONObject().put("interface", "wan").put("protocol", wanProtocol).put("ip_address", wanIp).put("netmask", wanNetmask).put("gateway", wanGateway).put("dns", wanDns).put("username", wanUsername).put("password", wanPassword) },
                modifier = Modifier.align(Alignment.End),
            ) { Text(stringResource(R.string.save_wan)) }
        }
    }
    if (capabilities["network.lan.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.lan_settings), "$lanIp · $lanNetmask") {
            OutlinedTextField(lanIp, { lanIp = it }, label = { Text(stringResource(R.string.router_ip)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(lanNetmask, { lanNetmask = it }, label = { Text(stringResource(R.string.netmask)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Button(
                onClick = { pendingCommand = "network.set_lan" to JSONObject().put("interface", "lan").put("ip_address", lanIp).put("netmask", lanNetmask) },
                modifier = Modifier.align(Alignment.End),
            ) { Text(stringResource(R.string.save_lan)) }
        }
    }
    if (capabilities["dns.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.dns_servers), dnsServers) {
            OutlinedTextField(dnsServers, { dnsServers = it }, label = { Text(stringResource(R.string.dns_servers)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Button(
                onClick = { pendingCommand = "dns.set_servers" to JSONObject().put("servers", dnsServers) },
                modifier = Modifier.align(Alignment.End),
            ) { Text(stringResource(R.string.apply_dns)) }
        }
    }
    if (capabilities["firewall.port_forward"] == true) {
        ExpandableSettingsCard(stringResource(R.string.port_forwarding), stringResource(R.string.port_forward_summary)) {
            OutlinedTextField(forwardName, { forwardName = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(forwardExternalPort, { forwardExternalPort = it }, label = { Text(stringResource(R.string.external_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(forwardInternalIp, { forwardInternalIp = it }, label = { Text(stringResource(R.string.internal_ip)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(forwardInternalPort, { forwardInternalPort = it }, label = { Text(stringResource(R.string.internal_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow {
                Button(
                    onClick = { pendingCommand = "firewall.set_port_forward" to JSONObject().put("name", forwardName).put("protocol", "tcp").put("external_port", forwardExternalPort).put("internal_ip", forwardInternalIp).put("internal_port", forwardInternalPort) },
                    enabled = forwardName.isNotBlank() && forwardExternalPort.isNotBlank() && forwardInternalIp.isNotBlank() && forwardInternalPort.isNotBlank(),
                ) { Text(stringResource(R.string.add_port_forward)) }
                TextButton(onClick = { pendingCommand = "firewall.delete_port_forward" to JSONObject().put("name", forwardName) }, enabled = forwardName.isNotBlank()) {
                    Text(stringResource(R.string.delete_port_forward))
                }
            }
        }
    }
    if (capabilities["network.interface_restart"] == true || capabilities["network.restart"] == true) {
        ExpandableSettingsCard(stringResource(R.string.network_maintenance), stringResource(R.string.network_maintenance_summary)) {
            if (capabilities["network.interface_restart"] == true) {
                OutlinedTextField(interfaceName, { interfaceName = it }, label = { Text(stringResource(R.string.network_interfaces)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedButton(
                    onClick = { pendingCommand = "network.interface_restart" to JSONObject().put("interface", interfaceName) },
                    enabled = interfaceName.isNotBlank(),
                    modifier = Modifier.align(Alignment.End),
                ) { Text(stringResource(R.string.restart_interface)) }
            }
            if (capabilities["network.restart"] == true) {
                OutlinedButton(onClick = { pendingCommand = "network.restart" to JSONObject() }, modifier = Modifier.align(Alignment.End)) {
                    Text(stringResource(R.string.restart_network))
                }
            }
        }
    }
    MessageBanner(message, error = messageIsError)
    pendingCommand?.let { command ->
        AlertDialog(
            onDismissRequest = { pendingCommand = null },
            title = { Text(stringResource(R.string.confirm_action)) },
            text = {
                Text(
                    if (command.first in setOf("network.restart", "network.interface_restart")) {
                        stringResource(R.string.network_restart_warning)
                    } else {
                        stringResource(R.string.config_backup_notice)
                    },
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    pendingCommand = null
                    val success = when (command.first) {
                        "network.restart" -> networkRestartQueued
                        "network.interface_restart" -> interfaceRestartQueued
                        else -> genericCommandQueued
                    }
                    queue(command.first, command.second, success)
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
    var messageIsError by remember { mutableStateOf(false) }
    var confirmReboot by remember { mutableStateOf(false) }
    var confirmAgentRollback by remember { mutableStateOf(false) }
    var hostnameValue by remember { mutableStateOf("") }
    var zoneName by remember { mutableStateOf("Europe/Moscow") }
    var timezoneValue by remember { mutableStateOf("MSK-3") }
    var ntpServers by remember { mutableStateOf("0.openwrt.pool.ntp.org, 1.openwrt.pool.ntp.org") }
    var pendingSystemCommand by remember { mutableStateOf<Pair<String, JSONObject>?>(null) }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    hostnameValue = result.data.system?.optString("hostname").orEmpty().ifBlank { device.hostname }
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getCommands(device.id) }) {
                is ApiResult.Success -> commands = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
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
    val systemCommandQueued = stringResource(R.string.command_queued)
    val updateCheckQueued = stringResource(R.string.update_check_queued)
    val intervalChangeQueued = stringResource(R.string.interval_change_queued)
    val autoUpdateEnableQueued = stringResource(R.string.auto_update_enable_queued)
    val autoUpdateDisableQueued = stringResource(R.string.auto_update_disable_queued)
    val rollbackQueued = stringResource(R.string.rollback_queued)

    fun queueSystem(type: String, payload: JSONObject, success: String) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, type, payload, true) }) {
                is ApiResult.Success -> { message = success; messageIsError = false; refresh() }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
        }
    }

    val uptimeLabel = formatDuration(system?.optLong("uptime", 0) ?: 0)
    val memoryLabel = memory?.let { "${it.optLong("available_kb") / 1024} / ${it.optLong("total_kb") / 1024} MB" } ?: stringResource(R.string.no_data)
    val storageLabel = storage?.let { "${it.optLong("used_kb") / 1024} / ${it.optLong("total_kb") / 1024} MB" } ?: stringResource(R.string.no_data)
    val connectionLabel = systemSummary?.let { "${it.optLong("conntrack_count")} / ${it.optLong("conntrack_max")}" } ?: stringResource(R.string.no_data)

    RouterPageHeader(
        title = stringResource(R.string.system),
        subtitle = stringResource(R.string.system_screen_summary),
        onRefresh = refresh,
    )
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        MetricTile(stringResource(R.string.uptime), uptimeLabel, Modifier.weight(1f))
        MetricTile(stringResource(R.string.load), system?.optString("load").orEmpty().ifBlank { stringResource(R.string.no_data) }, Modifier.weight(1f), MaterialTheme.colorScheme.tertiary)
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        MetricTile(stringResource(R.string.memory), memoryLabel, Modifier.weight(1f), MaterialTheme.colorScheme.secondary)
        MetricTile(stringResource(R.string.storage), storageLabel, Modifier.weight(1f))
    }
    SectionCard(stringResource(R.string.router_information)) {
        InfoRow(stringResource(R.string.hostname), hostnameValue, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.kernel), systemSummary?.optString("kernel"), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.connections), connectionLabel, stringResource(R.string.no_data))
    }
    if (services != null) {
        SectionCard(stringResource(R.string.services), subtitle = stringResource(R.string.services_summary)) {
            listOf("network", "dnsmasq", "firewall", "odhcpd").forEachIndexed { index, service ->
                val value = services.optString(service)
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(service, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                    StatusPill(value.ifBlank { stringResource(R.string.no_data) }, value.lowercase() in setOf("running", "active", "ok", "enabled", "true", "1"))
                }
                if (index < 3) HorizontalDivider()
            }
        }
    }
    if (capabilities["system.set_hostname"] == true) {
        ExpandableSettingsCard(stringResource(R.string.device_name), hostnameValue) {
            OutlinedTextField(hostnameValue, { hostnameValue = it }, label = { Text(stringResource(R.string.new_hostname)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Button(
                onClick = { pendingSystemCommand = "system.set_hostname" to JSONObject().put("hostname", hostnameValue) },
                enabled = hostnameValue.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            ) { Text(stringResource(R.string.change_hostname)) }
        }
    }
    if (capabilities["system.set_timezone"] == true || capabilities["system.set_ntp"] == true) {
        ExpandableSettingsCard(stringResource(R.string.time_settings), zoneName) {
            if (capabilities["system.set_timezone"] == true) {
                OutlinedTextField(zoneName, { zoneName = it }, label = { Text(stringResource(R.string.timezone_region)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(timezoneValue, { timezoneValue = it }, label = { Text("POSIX timezone") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(
                    onClick = { pendingSystemCommand = "system.set_timezone" to JSONObject().put("zonename", zoneName).put("timezone", timezoneValue) },
                    modifier = Modifier.align(Alignment.End),
                ) { Text(stringResource(R.string.save_time_settings)) }
            }
            if (capabilities["system.set_ntp"] == true) {
                HorizontalDivider()
                OutlinedTextField(ntpServers, { ntpServers = it }, label = { Text(stringResource(R.string.ntp_servers)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Button(
                    onClick = { pendingSystemCommand = "system.set_ntp" to JSONObject().put("enabled", true).put("servers", ntpServers) },
                    modifier = Modifier.align(Alignment.End),
                ) { Text(stringResource(R.string.apply_ntp)) }
            }
        }
    }
    if (capabilities["system.restart_service"] == true) {
        ExpandableSettingsCard(stringResource(R.string.service_management), stringResource(R.string.service_management_summary)) {
            listOf("dnsmasq", "firewall", "odhcpd", "network").forEach { service ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(service, modifier = Modifier.weight(1f))
                    TextButton(onClick = { pendingSystemCommand = "system.restart_service" to JSONObject().put("service", service) }) {
                        Text(stringResource(R.string.restart_service))
                    }
                }
            }
        }
    }
    SectionCard(stringResource(R.string.system_actions), subtitle = stringResource(R.string.system_actions_summary)) {
        ActionRow {
            if (capabilities["diagnostics.check_server"] == true) {
                FilledTonalButton(
                    onClick = {
                        scope.launch {
                            when (val result = withContext(Dispatchers.IO) {
                                WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, "diagnostics.run", JSONObject(), confirmed = true)
                            }) {
                                is ApiResult.Success -> { message = diagnosticsQueued; messageIsError = false; refresh() }
                                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                                    message = result.message
                                    messageIsError = true
                                }
                            }
                        }
                    },
                ) { Text(stringResource(R.string.diagnostics)) }
            }
            if (capabilities["system.reboot"] == true) {
                OutlinedButton(onClick = { confirmReboot = true }) { Text(stringResource(R.string.reboot)) }
            }
        }
        latestDiagnostics?.let {
            InfoRow(stringResource(R.string.last_diagnostics), it.status, stringResource(R.string.no_data))
        }
    }
    MessageBanner(message, error = messageIsError)
    AgentSection(
        agent = telemetry?.agent,
        actionError = "",
        onCheckUpdate = { queueSystem("agent.update", JSONObject(), updateCheckQueued) },
        onSetInterval = { seconds ->
            queueSystem("agent.set_interval", JSONObject().put("interval_seconds", seconds), intervalChangeQueued)
        },
        onEnableAutoUpdate = {
            queueSystem("agent.set_auto_update", JSONObject().put("enabled", true), autoUpdateEnableQueued)
        },
        onDisableAutoUpdate = {
            queueSystem("agent.set_auto_update", JSONObject().put("enabled", false), autoUpdateDisableQueued)
        },
        onRollback = { confirmAgentRollback = true },
    )
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
                            is ApiResult.Success -> { message = rebootQueued; messageIsError = false }
                            is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                                message = result.message
                                messageIsError = true
                            }
                        }
                    }
                },
            ) { Text(stringResource(R.string.reboot)) }
        },
        dismissButton = { TextButton(onClick = { confirmReboot = false }) { Text(stringResource(R.string.cancel)) } },
    )
    if (confirmAgentRollback) AlertDialog(
        onDismissRequest = { confirmAgentRollback = false },
        title = { Text(stringResource(R.string.rollback_confirm_title)) },
        text = { Text(stringResource(R.string.rollback_confirm_message)) },
        confirmButton = {
            TextButton(onClick = {
                confirmAgentRollback = false
                queueSystem("agent.rollback", JSONObject(), rollbackQueued)
            }) { Text(stringResource(R.string.rollback_action)) }
        },
        dismissButton = { TextButton(onClick = { confirmAgentRollback = false }) { Text(stringResource(R.string.cancel)) } },
    )
    pendingSystemCommand?.let { command ->
        AlertDialog(
            onDismissRequest = { pendingSystemCommand = null },
            title = { Text(stringResource(R.string.confirm_action)) },
            text = { Text(stringResource(R.string.config_backup_notice)) },
            confirmButton = {
                TextButton(onClick = {
                    pendingSystemCommand = null
                    val success = when (command.first) {
                        "system.set_hostname" -> hostnameQueued
                        "system.restart_service" -> serviceQueued
                        else -> systemCommandQueued
                    }
                    queueSystem(command.first, command.second, success)
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
