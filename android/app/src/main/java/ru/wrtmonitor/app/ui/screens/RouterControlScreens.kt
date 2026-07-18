package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
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
import ru.wrtmonitor.app.api.dto.CommandPreviewDto
import ru.wrtmonitor.app.api.dto.ClientProfileDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.NetworkClientDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.ui.components.InfoRow
import ru.wrtmonitor.app.ui.components.ActionRow
import ru.wrtmonitor.app.ui.components.ExpandableSettingsCard
import ru.wrtmonitor.app.ui.components.MessageBanner
import ru.wrtmonitor.app.ui.components.MetricTile
import ru.wrtmonitor.app.ui.components.MultiOptionSelector
import ru.wrtmonitor.app.ui.components.OptionSelector
import ru.wrtmonitor.app.ui.components.PrimaryActionButton
import ru.wrtmonitor.app.ui.components.RouterPageHeader
import ru.wrtmonitor.app.ui.components.SecondaryActionButton
import ru.wrtmonitor.app.ui.components.SectionCard
import ru.wrtmonitor.app.ui.components.StatusPill
import ru.wrtmonitor.app.ui.components.SwitchSettingRow
import ru.wrtmonitor.app.ui.components.TonalActionButton
import ru.wrtmonitor.app.ui.components.SelectOption

private data class PendingSafeCommand(
    val type: String,
    val payload: JSONObject,
    val successMessage: String = "",
)

private data class TimezoneOption(val zonename: String, val timezone: String, val label: String)

private val timezoneOptions = listOf(
    TimezoneOption("UTC", "UTC0", "UTC (UTC+0)"),
    TimezoneOption("Europe/Kaliningrad", "EET-2", "Europe/Kaliningrad (UTC+2)"),
    TimezoneOption("Europe/Moscow", "MSK-3", "Europe/Moscow (UTC+3)"),
    TimezoneOption("Europe/Samara", "<+04>-4", "Europe/Samara (UTC+4)"),
    TimezoneOption("Asia/Yekaterinburg", "<+05>-5", "Asia/Yekaterinburg (UTC+5)"),
    TimezoneOption("Asia/Omsk", "<+06>-6", "Asia/Omsk (UTC+6)"),
    TimezoneOption("Asia/Krasnoyarsk", "<+07>-7", "Asia/Krasnoyarsk (UTC+7)"),
    TimezoneOption("Asia/Irkutsk", "<+08>-8", "Asia/Irkutsk (UTC+8)"),
    TimezoneOption("Asia/Yakutsk", "<+09>-9", "Asia/Yakutsk (UTC+9)"),
    TimezoneOption("Asia/Vladivostok", "<+10>-10", "Asia/Vladivostok (UTC+10)"),
    TimezoneOption("Asia/Magadan", "<+11>-11", "Asia/Magadan (UTC+11)"),
    TimezoneOption("Asia/Kamchatka", "<+12>-12", "Asia/Kamchatka (UTC+12)"),
    TimezoneOption("Europe/London", "GMT0BST,M3.5.0/1,M10.5.0", "Europe/London"),
    TimezoneOption("Europe/Berlin", "CET-1CEST,M3.5.0,M10.5.0/3", "Europe/Berlin"),
    TimezoneOption("Europe/Kyiv", "EET-2EEST,M3.5.0/3,M10.5.0/4", "Europe/Kyiv"),
    TimezoneOption("Asia/Dubai", "<+04>-4", "Asia/Dubai"),
    TimezoneOption("Asia/Shanghai", "CST-8", "Asia/Shanghai"),
    TimezoneOption("Asia/Tokyo", "JST-9", "Asia/Tokyo"),
    TimezoneOption("America/New_York", "EST5EDT,M3.2.0,M11.1.0", "America/New_York"),
    TimezoneOption("America/Chicago", "CST6CDT,M3.2.0,M11.1.0", "America/Chicago"),
    TimezoneOption("America/Denver", "MST7MDT,M3.2.0,M11.1.0", "America/Denver"),
    TimezoneOption("America/Los_Angeles", "PST8PDT,M3.2.0,M11.1.0", "America/Los_Angeles"),
    TimezoneOption("Australia/Sydney", "AEST-10AEDT,M10.1.0,M4.1.0/3", "Australia/Sydney"),
)

private val netmaskOptions = (8..30).map { prefix ->
    val mask = (0xffffffffL shl (32 - prefix) and 0xffffffffL)
    SelectOption(
        value = listOf(24, 16, 8, 0).joinToString(".") { shift -> ((mask shr shift) and 0xff).toString() },
        label = "/$prefix · " + listOf(24, 16, 8, 0).joinToString(".") { shift -> ((mask shr shift) and 0xff).toString() },
    )
}

private val weekdayOptions = listOf("mon", "tue", "wed", "thu", "fri", "sat", "sun").map { SelectOption(it, it.uppercase()) }
private val priorityOptions = listOf("low", "normal", "high", "realtime").map { SelectOption(it, it) }
private val leaseTimeOptions = listOf("30m", "1h", "6h", "12h", "24h", "72h", "168h").map { SelectOption(it, it) }
private val wanProtocolOptions = listOf("dhcp", "static", "pppoe").map { SelectOption(it, it.uppercase()) }
private val wifiCountryOptions = listOf("RU", "BY", "KZ", "AM", "AZ", "GE", "KG", "UZ", "DE", "FR", "GB", "IT", "ES", "PL", "NL", "FI", "SE", "NO", "US", "CA", "CN", "JP", "KR", "AU").map { SelectOption(it, it) }
private val wifiChannelOptions = (
    listOf("auto") + (1..14).map(Int::toString) +
        listOf("36", "40", "44", "48", "52", "56", "60", "64", "100", "104", "108", "112", "116", "120", "124", "128", "132", "136", "140", "144", "149", "153", "157", "161", "165")
    ).map { SelectOption(it, if (it == "auto") "AUTO" else it) }
private fun wifiChannelOptionsForBand(band: String): List<SelectOption> {
    val values = when (band.lowercase()) {
        "2g" -> listOf("auto") + (1..13).map(Int::toString)
        "5g" -> listOf("auto", "36", "40", "44", "48", "52", "56", "60", "64", "100", "104", "108", "112", "116", "120", "124", "128", "132", "136", "140", "144", "149", "153", "157", "161", "165")
        else -> wifiChannelOptions.map(SelectOption::value)
    }
    return values.map { SelectOption(it, if (it == "auto") "AUTO" else it) }
}
private val wifiModeOptions = listOf("HE80", "HE40", "HE20", "VHT160", "VHT80", "VHT40", "VHT20", "HT40", "HT20").map { SelectOption(it, it) }
private val wifiEncryptionOptions = listOf("sae-mixed", "sae", "psk2", "none").map { SelectOption(it, it) }
private val ipv6PrefixOptions = listOf("48", "52", "56", "60", "64").map { SelectOption(it, "/$it") }
private val processSignalOptions = listOf("TERM", "HUP", "INT", "KILL").map { SelectOption(it, it) }

@Composable
private fun ClientPolicyCard(
    client: NetworkClientDto,
    profiles: List<ClientProfileDto>,
    canDeleteLease: Boolean,
    onDeleteLease: () -> Unit,
    onSave: (String, String?, JSONObject) -> Unit,
) {
    val policy = client.effectivePolicy
    val schedule = policy.optJSONObject("schedule") ?: JSONObject()
    val qos = policy.optJSONObject("qos") ?: JSONObject()
    var displayName by remember(client.id) { mutableStateOf(client.displayName.orEmpty()) }
    var profileId by remember(client.id) { mutableStateOf(client.profileId) }
    var blocked by remember(client.id) { mutableStateOf(policy.optBoolean("blocked")) }
    var scheduleEnabled by remember(client.id) { mutableStateOf(schedule.optBoolean("enabled")) }
    var weekdays by remember(client.id) {
        mutableStateOf(schedule.optJSONArray("weekdays")?.let { array ->
            (0 until array.length()).map { array.optString(it) }.filter(String::isNotBlank).toSet()
        } ?: emptySet())
    }
    var start by remember(client.id) { mutableStateOf(schedule.optString("start")) }
    var stop by remember(client.id) { mutableStateOf(schedule.optString("stop")) }
    var priority by remember(client.id) { mutableStateOf(qos.optString("priority", "normal")) }
    var download by remember(client.id) { mutableStateOf(qos.optInt("download_kbps").toString()) }
    var upload by remember(client.id) { mutableStateOf(qos.optInt("upload_kbps").toString()) }

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        displayName.ifBlank { client.hostname ?: stringResource(R.string.client_unknown) },
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(client.vendor ?: client.mac, style = MaterialTheme.typography.bodySmall)
                }
                StatusPill(
                    if (client.online) stringResource(R.string.online) else stringResource(R.string.offline),
                    client.online,
                )
            }
            InfoRow(stringResource(R.string.ip_address), client.ipAddress.orEmpty(), stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.mac_address), client.mac, stringResource(R.string.no_data))
            if (canDeleteLease && client.isStatic) {
                TextButton(onClick = onDeleteLease, modifier = Modifier.align(Alignment.End)) { Text(stringResource(R.string.delete_lease)) }
            }
            ExpandableSettingsCard(
                title = stringResource(R.string.client_access_policy),
                summary = if (blocked) stringResource(R.string.access_blocked) else stringResource(R.string.access_allowed),
            ) {
                OutlinedTextField(displayName, { displayName = it }, label = { Text(stringResource(R.string.device_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Text(stringResource(R.string.client_profile), style = MaterialTheme.typography.labelLarge)
                TextButton(onClick = { profileId = null }) { Text(if (profileId == null) stringResource(R.string.no_profile_selected) else stringResource(R.string.no_profile)) }
                profiles.forEach { profile ->
                    TextButton(onClick = { profileId = profile.id }) { Text(if (profileId == profile.id) "${profile.name} · ${stringResource(R.string.selected)}" else profile.name) }
                }
                SwitchSettingRow(stringResource(R.string.block_client), checked = blocked, onCheckedChange = { blocked = it })
                SwitchSettingRow(stringResource(R.string.access_schedule), checked = scheduleEnabled, onCheckedChange = { scheduleEnabled = it })
                if (scheduleEnabled) {
                    MultiOptionSelector(stringResource(R.string.schedule_weekdays), weekdays, weekdayOptions, { weekdays = it })
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(start, { start = it }, label = { Text(stringResource(R.string.schedule_start)) }, modifier = Modifier.weight(1f), singleLine = true)
                        OutlinedTextField(stop, { stop = it }, label = { Text(stringResource(R.string.schedule_stop)) }, modifier = Modifier.weight(1f), singleLine = true)
                    }
                }
                OptionSelector(stringResource(R.string.traffic_priority), priority, priorityOptions, { priority = it })
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(download, { download = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.download_limit)) }, modifier = Modifier.weight(1f), singleLine = true)
                    OutlinedTextField(upload, { upload = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.upload_limit)) }, modifier = Modifier.weight(1f), singleLine = true)
                }
                PrimaryActionButton(
                    label = stringResource(R.string.save_policy),
                    onClick = {
                        val days = JSONArray()
                        weekdays.sorted().forEach(days::put)
                        onSave(
                            displayName,
                            profileId,
                            JSONObject()
                                .put("blocked", blocked)
                                .put("schedule", JSONObject().put("enabled", scheduleEnabled).put("weekdays", days).put("start", start).put("stop", stop))
                                .put("qos", JSONObject().put("priority", priority).put("download_kbps", download.toIntOrNull() ?: 0).put("upload_kbps", upload.toIntOrNull() ?: 0)),
                        )
                    },
                    modifier = Modifier.align(Alignment.End),
                )
            }
        }
    }
}

@Composable
private fun SafeCommandDialog(
    serverUrl: String,
    accessToken: String,
    deviceId: String,
    command: PendingSafeCommand,
    onDismiss: () -> Unit,
    onApply: () -> Unit,
    onSessionExpired: () -> Unit,
) {
    var preview by remember(command.type, command.payload.toString()) { mutableStateOf<CommandPreviewDto?>(null) }
    var error by remember(command.type, command.payload.toString()) { mutableStateOf("") }
    LaunchedEffect(command.type, command.payload.toString()) {
        when (val result = withContext(Dispatchers.IO) {
            WrtMonitorApi(serverUrl, accessToken).previewCommand(deviceId, command.type, command.payload)
        }) {
            is ApiResult.Success -> preview = result.data
            is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else error = result.message
        }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.safe_apply_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                when {
                    error.isNotBlank() -> Text(error, color = MaterialTheme.colorScheme.error)
                    preview == null -> CircularProgressIndicator()
                    else -> {
                        preview?.changes?.forEach { change ->
                            Text(change.field, style = MaterialTheme.typography.labelLarge)
                            Text("${change.current}  →  ${change.proposed}", style = MaterialTheme.typography.bodyMedium)
                        }
                        preview?.warnings?.forEach { warning ->
                            Text(warning, color = MaterialTheme.colorScheme.tertiary)
                        }
                        preview?.errors?.forEach { item ->
                            Text(item, color = MaterialTheme.colorScheme.error)
                        }
                        if (preview?.transactional == true) {
                            Text(
                                stringResource(R.string.rollback_timeout, preview?.rollbackTimeoutSeconds ?: 90),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onApply, enabled = preview?.canApply == true) {
                Text(stringResource(R.string.apply))
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) } },
    )
}

@Composable
fun ClientsControlScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var networkClients by remember { mutableStateOf<List<NetworkClientDto>>(emptyList()) }
    var clientProfiles by remember { mutableStateOf<List<ClientProfileDto>>(emptyList()) }
    var profileName by remember { mutableStateOf("") }
    var profileBlocked by remember { mutableStateOf(false) }
    var hostname by remember { mutableStateOf("") }
    var mac by remember { mutableStateOf("") }
    var ip by remember { mutableStateOf("") }
    var poolStart by remember { mutableStateOf("") }
    var poolLimit by remember { mutableStateOf("") }
    var leaseTime by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var messageIsError by remember { mutableStateOf(false) }
    var pendingCommand by remember { mutableStateOf<PendingSafeCommand?>(null) }
    var dhcpInitialized by remember(device.id) { mutableStateOf(false) }
    val leaseQueuedText = stringResource(R.string.lease_queued)
    val genericQueuedText = stringResource(R.string.command_queued)

    val refresh: () -> Unit = {
        scope.launch {
            val api = WrtMonitorApi(serverUrl, accessToken)
            when (val result = withContext(Dispatchers.IO) { api.getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    if (!dhcpInitialized) {
                        val pools = result.data.payload?.optJSONObject("dhcp")?.optJSONArray("pools")
                        val lanPool = pools?.let { array ->
                            (0 until array.length()).mapNotNull(array::optJSONObject)
                                .firstOrNull { it.optString("interface") == "lan" }
                        }
                        if (lanPool != null) {
                            poolStart = lanPool.optInt("start").takeIf { it > 0 }?.toString().orEmpty()
                            poolLimit = lanPool.optInt("limit").takeIf { it > 0 }?.toString().orEmpty()
                            leaseTime = lanPool.optString("leasetime")
                        }
                        dhcpInitialized = true
                    }
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            when (val result = withContext(Dispatchers.IO) { api.getNetworkClients(device.id) }) {
                is ApiResult.Success -> networkClients = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            when (val result = withContext(Dispatchers.IO) { api.getClientProfiles(device.id) }) {
                is ApiResult.Success -> clientProfiles = result.data
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
    val clients = networkClients
    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()

    RouterPageHeader(
        title = stringResource(R.string.home_network),
        subtitle = stringResource(R.string.clients_found, clients.size),
        onRefresh = refresh,
    )
    if (clients.isEmpty()) {
        Card(Modifier.fillMaxWidth()) { Text(stringResource(R.string.no_data), Modifier.padding(16.dp)) }
    }
    for (client in clients) {
        ClientPolicyCard(
            client,
            clientProfiles,
            canDeleteLease = capabilities["dhcp.delete_lease"] == true,
            onDeleteLease = { pendingCommand = PendingSafeCommand("dhcp.delete_lease", JSONObject().put("mac", client.mac), genericQueuedText) },
        ) { displayName, profileId, policy ->
            scope.launch {
                val api = WrtMonitorApi(serverUrl, accessToken)
                val storedPolicy = if (profileId == null) policy else JSONObject()
                when (val update = withContext(Dispatchers.IO) { api.updateNetworkClient(device.id, client.id, displayName, profileId, storedPolicy) }) {
                    is ApiResult.Success -> when (val apply = withContext(Dispatchers.IO) { api.applyNetworkClientPolicy(device.id, client.id) }) {
                        is ApiResult.Success -> { message = genericQueuedText; messageIsError = false; refresh() }
                        is ApiResult.Error -> if (apply.isUnauthorized()) onSessionExpired() else { message = apply.message; messageIsError = true }
                    }
                    is ApiResult.Error -> if (update.isUnauthorized()) onSessionExpired() else { message = update.message; messageIsError = true }
                }
            }
        }
    }

    if (capabilities["clients.policy"] == true) {
        ExpandableSettingsCard(stringResource(R.string.access_profiles), stringResource(R.string.profiles_count, clientProfiles.size)) {
            clientProfiles.forEach { profile ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(profile.name, modifier = Modifier.weight(1f))
                    TextButton(onClick = {
                        scope.launch {
                            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).deleteClientProfile(device.id, profile.id) }) {
                                is ApiResult.Success -> refresh()
                                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else { message = result.message; messageIsError = true }
                            }
                        }
                    }) { Text(stringResource(R.string.delete)) }
                }
            }
            OutlinedTextField(profileName, { profileName = it }, label = { Text(stringResource(R.string.profile_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            SwitchSettingRow(stringResource(R.string.block_client), checked = profileBlocked, onCheckedChange = { profileBlocked = it })
            PrimaryActionButton(
                label = stringResource(R.string.create_profile),
                onClick = {
                    scope.launch {
                        when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).createClientProfile(device.id, profileName, profileBlocked) }) {
                            is ApiResult.Success -> { profileName = ""; profileBlocked = false; refresh() }
                            is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else { message = result.message; messageIsError = true }
                        }
                    }
                },
                enabled = profileName.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            )
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
            PrimaryActionButton(
                label = stringResource(R.string.save_lease),
                onClick = { pendingCommand = PendingSafeCommand("dhcp.set_lease", JSONObject().put("hostname", hostname).put("mac", mac).put("ip", ip), leaseQueuedText) },
                enabled = hostname.isNotBlank() && mac.length >= 17 && ip.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (capabilities["dhcp.configure"] == true) {
        ExpandableSettingsCard(
            title = stringResource(R.string.dhcp_pool),
            summary = "$poolStart · $poolLimit · $leaseTime",
        ) {
            OutlinedTextField(poolStart, { poolStart = it }, label = { Text(stringResource(R.string.pool_start)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(poolLimit, { poolLimit = it }, label = { Text(stringResource(R.string.pool_size)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OptionSelector(stringResource(R.string.lease_time), leaseTime, leaseTimeOptions, { leaseTime = it })
            PrimaryActionButton(
                label = stringResource(R.string.save_dhcp),
                onClick = { pendingCommand = PendingSafeCommand("dhcp.set_pool", JSONObject().put("interface", "lan").put("start", poolStart).put("limit", poolLimit).put("leasetime", leaseTime), genericQueuedText) },
                enabled = poolStart.isNotBlank() && poolLimit.isNotBlank() && leaseTime.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    MessageBanner(message, error = messageIsError)

    pendingCommand?.let { command -> SafeCommandDialog(
        serverUrl, accessToken, device.id, command,
        onDismiss = { pendingCommand = null },
        onApply = { pendingCommand = null; queue(command.type, command.payload) },
        onSessionExpired = onSessionExpired,
    ) }
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
    var guestSsid by remember { mutableStateOf("") }
    var guestPassword by remember { mutableStateOf("") }
    var guestEnabled by remember { mutableStateOf(true) }
    var htmode by remember { mutableStateOf("") }
    var txpower by remember { mutableStateOf("") }
    var newSsid by remember { mutableStateOf("") }
    var newNetwork by remember { mutableStateOf("") }
    var newEncryption by remember { mutableStateOf("sae-mixed") }
    var newPassword by remember { mutableStateOf("") }
    var scheduleEnabled by remember { mutableStateOf(false) }
    var scheduleDays by remember { mutableStateOf(weekdayOptions.map { it.value }.toSet()) }
    var scheduleStart by remember { mutableStateOf("07:00") }
    var scheduleStop by remember { mutableStateOf("23:00") }
    var meshEnabled by remember { mutableStateOf(false) }
    var meshId by remember { mutableStateOf("") }
    var meshPassword by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var messageIsError by remember { mutableStateOf(false) }
    var pendingCommand by remember { mutableStateOf<PendingSafeCommand?>(null) }
    var selectedRadioId by remember(device.id) { mutableStateOf("") }
    var selectedInterfaceId by remember(device.id) { mutableStateOf("") }

    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    if (selectedRadioId.isBlank()) selectedRadioId = firstRadio(result.data)?.optString("id").orEmpty()
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
    val wifiSsidQueued = stringResource(R.string.wifi_ssid_queued)
    val wifiPasswordQueued = stringResource(R.string.wifi_password_queued)
    val wifiToggleQueued = stringResource(R.string.wifi_toggle_queued)
    val wifiChannelQueued = stringResource(R.string.wifi_channel_queued)
    val wifiCountryQueued = stringResource(R.string.wifi_country_queued)

    val radios = wifi?.optJSONArray("radios") ?: JSONArray()
    val radio = findRadio(radios, selectedRadioId) ?: radios.optJSONObject(0)
    val radioId = radio?.optString("id").takeUnless { it.isNullOrBlank() } ?: "radio0"
    val interfaces = radio?.optJSONArray("interfaces") ?: JSONArray()
    val iface = findInterface(interfaces, selectedInterfaceId) ?: interfaces.optJSONObject(0)
    val ifaceId = iface?.optString("id").takeUnless { it.isNullOrBlank() }
    val radioOptions = (0 until radios.length()).mapNotNull(radios::optJSONObject).mapIndexed { index, item ->
        val id = item.optString("id").ifBlank { "radio$index" }
        SelectOption(id, listOf(item.optString("band"), item.optString("name").ifBlank { id }).filter(String::isNotBlank).joinToString(" · "))
    }
    val interfaceOptions = (0 until interfaces.length()).mapNotNull(interfaces::optJSONObject).map { item ->
        val id = item.optString("id")
        SelectOption(id, item.optString("ssid").ifBlank { id })
    }
    val networkOptions = telemetry?.network?.optJSONArray("interfaces")?.let { array ->
        (0 until array.length()).mapNotNull(array::optJSONObject)
            .map { it.optString("interface") }.filter(String::isNotBlank).distinct()
            .map { SelectOption(it, it) }
    }.orEmpty()
    LaunchedEffect(telemetry, selectedRadioId) {
        val selected = findRadio(radios, selectedRadioId) ?: radios.optJSONObject(0) ?: return@LaunchedEffect
        if (selectedRadioId != selected.optString("id")) selectedRadioId = selected.optString("id")
        enabled = selected.optBoolean("up", true)
        channel = selected.optString("channel").ifBlank { "auto" }
        country = selected.optString("country")
        htmode = selected.optString("htmode")
        txpower = selected.optString("txpower")
        val selectedIface = selected.optJSONArray("interfaces")?.optJSONObject(0)
        selectedInterfaceId = selectedIface?.optString("id").orEmpty()
        ssid = selectedIface?.optString("ssid").orEmpty()
        newNetwork = selectedIface?.optString("network").orEmpty()
        val schedule = selected.optJSONObject("schedule")
        scheduleEnabled = schedule?.optBoolean("enabled") ?: false
        scheduleDays = schedule?.optJSONArray("weekdays")?.let { array ->
            (0 until array.length()).map { array.optString(it) }.filter(String::isNotBlank).toSet()
        } ?: scheduleDays
        scheduleStart = schedule?.optString("start").orEmpty().ifBlank { scheduleStart }
        scheduleStop = schedule?.optString("stop").orEmpty().ifBlank { scheduleStop }
    }
    LaunchedEffect(selectedInterfaceId) {
        val selected = findInterface(interfaces, selectedInterfaceId) ?: return@LaunchedEffect
        ssid = selected.optString("ssid")
        newNetwork = selected.optString("network")
    }
    RouterPageHeader(
        title = stringResource(R.string.wifi),
        subtitle = stringResource(R.string.wifi_screen_summary),
        onRefresh = refresh,
    )
    if (radioOptions.isNotEmpty()) {
        SectionCard(title = stringResource(R.string.wifi_selected_radio), subtitle = radio?.optString("name").orEmpty()) {
            OptionSelector(stringResource(R.string.wifi_radio), selectedRadioId, radioOptions, { selectedRadioId = it })
        }
    }
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

    if (capabilities["wifi.manage_ssid"] == true) {
        SectionCard(title = stringResource(R.string.wifi_networks), subtitle = stringResource(R.string.radio_count_value, interfaces.length())) {
            for (index in 0 until interfaces.length()) {
                val networkItem = interfaces.optJSONObject(index) ?: continue
                val networkId = networkItem.optString("id")
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(networkItem.optString("ssid").ifBlank { networkId }, style = MaterialTheme.typography.titleSmall)
                        Text(listOf(networkItem.optString("network"), networkItem.optString("encryption")).filter(String::isNotBlank).joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    SecondaryActionButton(
                        label = stringResource(R.string.wifi_delete_network),
                        onClick = { pendingCommand = PendingSafeCommand("wifi.delete_ssid", JSONObject().put("iface", networkId), wifiToggleQueued) },
                    )
                }
                if (index < interfaces.length() - 1) HorizontalDivider()
            }
        }
        ExpandableSettingsCard(title = stringResource(R.string.wifi_add_network), summary = newSsid) {
            OutlinedTextField(newSsid, { newSsid = it }, label = { Text("SSID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OptionSelector(stringResource(R.string.wifi_network_name), newNetwork, networkOptions, { newNetwork = it })
            OptionSelector(stringResource(R.string.wifi_encryption), newEncryption, wifiEncryptionOptions, { newEncryption = it })
            OutlinedTextField(newPassword, { newPassword = it }, label = { Text(stringResource(R.string.wifi_password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
            PrimaryActionButton(
                label = stringResource(R.string.wifi_add_network),
                onClick = { pendingCommand = PendingSafeCommand("wifi.add_ssid", JSONObject().put("radio", radioId).put("ssid", newSsid).put("network", newNetwork).put("encryption", newEncryption).put("key", newPassword).put("hidden", false).put("isolate", false), wifiToggleQueued) },
                enabled = newSsid.isNotBlank() && newNetwork.isNotBlank() && (newEncryption == "none" || newPassword.length >= 8),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }

    if (capabilities["wifi.radio.configure"] == true) {
        ExpandableSettingsCard(title = stringResource(R.string.wifi_radio_advanced), summary = listOf(channel, htmode, country).filter(String::isNotBlank).joinToString(" · ")) {
            OptionSelector(stringResource(R.string.wifi_channel), channel, wifiChannelOptionsForBand(radio?.optString("band").orEmpty()), { channel = it })
            OptionSelector(stringResource(R.string.wifi_width_mode), htmode, wifiModeOptions, { htmode = it })
            OptionSelector(stringResource(R.string.wifi_country), country, wifiCountryOptions, { country = it })
            OutlinedTextField(txpower, { txpower = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.wifi_txpower)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(label = stringResource(R.string.save), onClick = {
                val payload = JSONObject().put("radio", radioId).put("channel", channel).put("htmode", htmode).put("country", country)
                txpower.toIntOrNull()?.let { payload.put("txpower", it) }
                pendingCommand = PendingSafeCommand("wifi.set_radio", payload, wifiToggleQueued)
            }, modifier = Modifier.align(Alignment.End))
        }
    }

    if (capabilities["wifi.schedule"] == true) {
        ExpandableSettingsCard(title = stringResource(R.string.wifi_schedule), summary = "$scheduleStart–$scheduleStop") {
            SwitchSettingRow(stringResource(R.string.wifi_schedule), checked = scheduleEnabled, onCheckedChange = { scheduleEnabled = it })
            MultiOptionSelector(stringResource(R.string.wifi_weekdays_hint), scheduleDays, weekdayOptions, { scheduleDays = it })
            OutlinedTextField(scheduleStart, { scheduleStart = it }, label = { Text(stringResource(R.string.wifi_start_time)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(scheduleStop, { scheduleStop = it }, label = { Text(stringResource(R.string.wifi_stop_time)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(label = stringResource(R.string.save), onClick = { pendingCommand = PendingSafeCommand("wifi.set_schedule", JSONObject().put("radio", radioId).put("enabled", scheduleEnabled).put("weekdays", JSONArray(scheduleDays.sorted())).put("start", scheduleStart).put("stop", scheduleStop), wifiToggleQueued) }, modifier = Modifier.align(Alignment.End))
        }
    }

    if (capabilities["wifi.mesh"] == true) {
        ExpandableSettingsCard(title = stringResource(R.string.wifi_mesh), summary = meshId) {
            SwitchSettingRow(stringResource(R.string.wifi_state), checked = meshEnabled, onCheckedChange = { meshEnabled = it })
            OutlinedTextField(meshId, { meshId = it }, label = { Text(stringResource(R.string.wifi_mesh_id)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(meshPassword, { meshPassword = it }, label = { Text(stringResource(R.string.wifi_password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
            PrimaryActionButton(label = stringResource(R.string.save), onClick = { pendingCommand = PendingSafeCommand("wifi.set_mesh", JSONObject().put("radio", radioId).put("enabled", meshEnabled).put("mesh_id", meshId).put("network", "lan").put("encryption", "sae").put("key", meshPassword), wifiToggleQueued) }, enabled = !meshEnabled || (meshId.isNotBlank() && meshPassword.length >= 8), modifier = Modifier.align(Alignment.End))
        }
    }

    val stationGroups = wifi?.optJSONArray("stations") ?: JSONArray()
    if (stationGroups.length() > 0) {
        SectionCard(title = stringResource(R.string.wifi_stations)) {
            for (stationIndex in 0 until stationGroups.length()) {
                val station = stationGroups.optJSONObject(stationIndex) ?: continue
                val mac = station.optString("mac")
                InfoRow(mac, listOfNotNull(station.optInt("signal").takeIf { station.has("signal") }?.let { "$it dBm" }, station.optString("tx_bitrate").takeIf(String::isNotBlank)).joinToString(" · "))
            }
        }
    }

    if (capabilities["wifi.set_ssid"] == true || capabilities["wifi.set_password"] == true || capabilities["wifi.enable"] == true || capabilities["wifi.disable"] == true) {
        SectionCard(
            title = stringResource(R.string.main_wifi_network),
            subtitle = iface?.optString("ssid").orEmpty().ifBlank { stringResource(R.string.no_data) },
        ) {
            if (interfaceOptions.size > 1) {
                OptionSelector(stringResource(R.string.wifi_network_name), selectedInterfaceId, interfaceOptions, { selectedInterfaceId = it })
                HorizontalDivider()
            }
            if (capabilities["wifi.enable"] == true || capabilities["wifi.disable"] == true) {
                SwitchSettingRow(
                    title = stringResource(R.string.wifi_state),
                    subtitle = if (enabled) stringResource(R.string.wifi_enabled_state) else stringResource(R.string.wifi_disabled_state),
                    checked = enabled,
                    onCheckedChange = { enabled = it },
                )
                SecondaryActionButton(
                    label = stringResource(R.string.wifi_state_apply),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_enabled", JSONObject().put("enabled", enabled).put("radio", radioId), wifiToggleQueued) },
                    modifier = Modifier.align(Alignment.End),
                )
            }
            if (capabilities["wifi.set_ssid"] == true) {
                HorizontalDivider()
                OutlinedTextField(ssid, { ssid = it }, label = { Text("SSID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                PrimaryActionButton(
                    label = stringResource(R.string.apply_ssid),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_ssid", JSONObject().put("ssid", ssid).put("iface", ifaceId), wifiSsidQueued) },
                    modifier = Modifier.align(Alignment.End),
                    enabled = ssid.isNotBlank(),
                )
            }
            if (capabilities["wifi.set_password"] == true) {
                HorizontalDivider()
                OutlinedTextField(password, { password = it }, label = { Text(stringResource(R.string.new_wifi_password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
                PrimaryActionButton(
                    label = stringResource(R.string.change_password),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_password", JSONObject().put("password", password).put("iface", ifaceId), wifiPasswordQueued) },
                    modifier = Modifier.align(Alignment.End),
                    enabled = password.length >= 8,
                )
            }
        }
    }

    if (capabilities["wifi.radio.configure"] != true && (capabilities["wifi.set_channel"] == true || capabilities["wifi.set_country"] == true)) {
        ExpandableSettingsCard(
            title = stringResource(R.string.wifi_radio_settings),
            summary = listOf(channel, country).filter(String::isNotBlank).joinToString(" · "),
        ) {
            if (capabilities["wifi.set_channel"] == true) {
                OptionSelector(stringResource(R.string.wifi_channel), channel, wifiChannelOptionsForBand(radio?.optString("band").orEmpty()), { channel = it })
                PrimaryActionButton(
                    label = stringResource(R.string.change_channel),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_channel", JSONObject().put("channel", channel).put("radio", radioId), wifiChannelQueued) },
                    enabled = channel.isNotBlank(),
                    modifier = Modifier.align(Alignment.End),
                )
            }
            if (capabilities["wifi.set_country"] == true) {
                OptionSelector(stringResource(R.string.wifi_country), country, wifiCountryOptions, { country = it })
                PrimaryActionButton(
                    label = stringResource(R.string.change_country),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_country", JSONObject().put("country", country).put("radio", radioId), wifiCountryQueued) },
                    enabled = country.length == 2,
                    modifier = Modifier.align(Alignment.End),
                )
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
            PrimaryActionButton(
                label = stringResource(R.string.apply_guest_wifi),
                onClick = { pendingCommand = PendingSafeCommand("wifi.set_guest", JSONObject().put("enabled", guestEnabled).put("ssid", guestSsid).put("password", guestPassword).put("radio", radioId), wifiToggleQueued) },
                enabled = !guestEnabled || (guestSsid.isNotBlank() && guestPassword.length >= 8),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }

    if (capabilities.isEmpty()) MessageBanner(stringResource(R.string.capabilities_missing_reinstall))
    MessageBanner(message, error = messageIsError)

    pendingCommand?.let { command -> SafeCommandDialog(
        serverUrl, accessToken, device.id, command,
        onDismiss = { pendingCommand = null },
        onApply = {
            pendingCommand = null
            queue(command.type, command.payload, command.successMessage)
        },
        onSessionExpired = onSessionExpired,
    ) }
}

enum class NetworkScreenMode {
    Internet,
    Rules,
    Vpn,
}

@Composable
fun NetworkControlScreen(
    serverUrl: String,
    accessToken: String,
    device: DeviceDto,
    onSessionExpired: () -> Unit,
    mode: NetworkScreenMode = NetworkScreenMode.Internet,
) {
    val scope = rememberCoroutineScope()
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var message by remember { mutableStateOf("") }
    var messageIsError by remember { mutableStateOf(false) }
    var interfaceName by remember { mutableStateOf("") }
    var wanProtocol by remember { mutableStateOf("") }
    var wanIp by remember { mutableStateOf("") }
    var wanNetmask by remember { mutableStateOf("") }
    var wanGateway by remember { mutableStateOf("") }
    var wanDns by remember { mutableStateOf("") }
    var wanUsername by remember { mutableStateOf("") }
    var wanPassword by remember { mutableStateOf("") }
    var lanIp by remember { mutableStateOf("") }
    var lanNetmask by remember { mutableStateOf("") }
    var dnsServers by remember { mutableStateOf("") }
    var forwardName by remember { mutableStateOf("") }
    var forwardExternalPort by remember { mutableStateOf("") }
    var forwardInternalIp by remember { mutableStateOf("") }
    var forwardInternalPort by remember { mutableStateOf("") }
    var sqmEnabled by remember { mutableStateOf(true) }
    var sqmInterface by remember { mutableStateOf("") }
    var sqmDownload by remember { mutableStateOf("") }
    var sqmUpload by remember { mutableStateOf("") }
    var ipv6Enabled by remember { mutableStateOf(true) }
    var ipv6Prefix by remember { mutableStateOf("64") }
    var multiWanEnabled by remember { mutableStateOf(true) }
    var primaryWan by remember { mutableStateOf("") }
    var secondaryWan by remember { mutableStateOf("") }
    var routeName by remember { mutableStateOf("") }
    var routeTarget by remember { mutableStateOf("") }
    var routeGateway by remember { mutableStateOf("") }
    var routeMetric by remember { mutableStateOf("0") }
    var ddnsName by remember { mutableStateOf("") }
    var ddnsProvider by remember { mutableStateOf("") }
    var ddnsDomain by remember { mutableStateOf("") }
    var ddnsUser by remember { mutableStateOf("") }
    var ddnsPassword by remember { mutableStateOf("") }
    var upnpEnabled by remember { mutableStateOf(false) }
    var upnpSecure by remember { mutableStateOf(true) }
    var zoneNameValue by remember { mutableStateOf("") }
    var zoneNetworks by remember { mutableStateOf("") }
    var ruleNameValue by remember { mutableStateOf("") }
    var ruleSource by remember { mutableStateOf("") }
    var ruleDestination by remember { mutableStateOf("") }
    var rulePort by remember { mutableStateOf("") }
    var wgName by remember { mutableStateOf("") }
    var wgAddress by remember { mutableStateOf("") }
    var wgPort by remember { mutableStateOf("51820") }
    var wgPrivateKey by remember { mutableStateOf("") }
    var wgPeerName by remember { mutableStateOf("") }
    var wgPeerPublicKey by remember { mutableStateOf("") }
    var wgPeerPresharedKey by remember { mutableStateOf("") }
    var wgPeerAllowedIps by remember { mutableStateOf("") }
    var wgPeerEndpoint by remember { mutableStateOf("") }
    var openVpnName by remember { mutableStateOf("") }
    var openVpnConfig by remember { mutableStateOf("") }
    var vpnPolicyName by remember { mutableStateOf("") }
    var vpnPolicyInterface by remember { mutableStateOf("") }
    var vpnPolicySource by remember { mutableStateOf("") }
    var vpnPolicyDestination by remember { mutableStateOf("") }
    var pendingCommand by remember { mutableStateOf<PendingSafeCommand?>(null) }
    var formInitialized by remember(device.id) { mutableStateOf(false) }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    if (!formInitialized) {
                        val items = result.data.network?.optJSONArray("interfaces")
                        fun findInterface(name: String): JSONObject? = items?.let { array ->
                            (0 until array.length()).mapNotNull(array::optJSONObject)
                                .firstOrNull { it.optString("interface") == name }
                        }
                        val lan = findInterface("lan")
                        val wan = findInterface("wan")
                        lanIp = lan?.optJSONArray("ipv4")?.optString(0).orEmpty()
                        lanNetmask = lan?.optString("netmask").orEmpty()
                        wanProtocol = wan?.optString("proto").orEmpty()
                        wanIp = wan?.optJSONArray("ipv4")?.optString(0).orEmpty()
                        wanNetmask = wan?.optString("netmask").orEmpty()
                        wanGateway = wan?.optString("gateway").orEmpty()
                        wanDns = wan?.optJSONArray("dns")?.let { array ->
                            (0 until array.length()).joinToString(", ") { array.optString(it) }
                        }.orEmpty()
                        dnsServers = wanDns
                        interfaceName = wan?.optString("interface").orEmpty()
                        sqmInterface = wan?.optString("device").orEmpty()
                        primaryWan = wan?.optString("interface").orEmpty()
                        formInitialized = true
                    }
                }
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
    val interfaceOptions = interfaces?.let { array ->
        (0 until array.length()).mapNotNull(array::optJSONObject)
            .flatMap { listOf(it.optString("interface"), it.optString("device")) }
            .filter(String::isNotBlank).distinct().map { SelectOption(it, it) }
    }.orEmpty()
    val firewallZoneOptions = telemetry?.network?.optJSONArray("firewall_zones")?.let { array ->
        (0 until array.length()).mapNotNull(array::optJSONObject)
            .map { it.optString("name") }
            .filter(String::isNotBlank)
            .distinct()
            .map { SelectOption(it, it) }
    }.orEmpty()
    val vpn = telemetry?.payload?.optJSONObject("vpn")
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
        title = stringResource(
            when (mode) {
                NetworkScreenMode.Internet -> R.string.internet
                NetworkScreenMode.Rules -> R.string.network_rules
                NetworkScreenMode.Vpn -> R.string.vpn_title
            },
        ),
        subtitle = stringResource(
            when (mode) {
                NetworkScreenMode.Internet -> R.string.internet_screen_summary
                NetworkScreenMode.Rules -> R.string.network_rules_summary
                NetworkScreenMode.Vpn -> R.string.vpn_summary
            },
        ),
        onRefresh = refresh,
    )
    val sectionAvailable = when (mode) {
        NetworkScreenMode.Internet -> capabilities.keys.any {
            it.startsWith("network.") || it == "dns.configure" || it == "qos.sqm"
        }
        NetworkScreenMode.Rules -> capabilities.keys.any {
            it.startsWith("firewall.") || it == "network.routes.configure"
        }
        NetworkScreenMode.Vpn -> capabilities.keys.any { it.startsWith("vpn.") }
    }
    if (!sectionAvailable) {
        SectionCard(stringResource(R.string.status)) {
            Text(
                stringResource(R.string.capabilities_missing_reinstall),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
    if (mode == NetworkScreenMode.Vpn && (capabilities["telemetry.vpn"] == true || vpn != null)) {
        val wireguardCount = vpn?.optJSONObject("wireguard")?.optJSONArray("interfaces")?.length() ?: 0
        val openVpnService = vpn?.optJSONObject("openvpn")?.optString("service") ?: stringResource(R.string.no_data)
        val policyService = vpn?.optJSONObject("policy")?.optString("service") ?: stringResource(R.string.no_data)
        SectionCard(stringResource(R.string.vpn_title), subtitle = stringResource(R.string.vpn_summary)) {
            InfoRow(stringResource(R.string.wireguard), wireguardCount.toString())
            InfoRow(stringResource(R.string.openvpn), openVpnService)
            InfoRow(stringResource(R.string.policy_routing), policyService)
        }
    }
    if (mode == NetworkScreenMode.Internet) SectionCard(
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
            SecondaryActionButton(
                label = stringResource(R.string.request_interfaces),
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
            )
        }
    }

    if (mode == NetworkScreenMode.Internet && capabilities["network.wan.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.wan_settings), wanProtocol.uppercase()) {
            OptionSelector(stringResource(R.string.connection_type), wanProtocol, wanProtocolOptions, { wanProtocol = it })
            if (wanProtocol == "static") {
                OutlinedTextField(wanIp, { wanIp = it }, label = { Text(stringResource(R.string.ip_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OptionSelector(stringResource(R.string.netmask), wanNetmask, netmaskOptions, { wanNetmask = it })
                OutlinedTextField(wanGateway, { wanGateway = it }, label = { Text(stringResource(R.string.gateway)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            }
            if (wanProtocol == "pppoe") {
                OutlinedTextField(wanUsername, { wanUsername = it }, label = { Text(stringResource(R.string.username)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(wanPassword, { wanPassword = it }, label = { Text(stringResource(R.string.password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
            }
            OutlinedTextField(wanDns, { wanDns = it }, label = { Text(stringResource(R.string.dns_servers)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(
                label = stringResource(R.string.save_wan),
                onClick = { pendingCommand = PendingSafeCommand("network.set_wan", JSONObject().put("interface", "wan").put("protocol", wanProtocol).put("ip_address", wanIp).put("netmask", wanNetmask).put("gateway", wanGateway).put("dns", wanDns).put("username", wanUsername).put("password", wanPassword), genericCommandQueued) },
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["network.lan.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.lan_settings), "$lanIp · $lanNetmask") {
            OutlinedTextField(lanIp, { lanIp = it }, label = { Text(stringResource(R.string.router_ip)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OptionSelector(stringResource(R.string.netmask), lanNetmask, netmaskOptions, { lanNetmask = it })
            PrimaryActionButton(
                label = stringResource(R.string.save_lan),
                onClick = { pendingCommand = PendingSafeCommand("network.set_lan", JSONObject().put("interface", "lan").put("ip_address", lanIp).put("netmask", lanNetmask), genericCommandQueued) },
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["dns.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.dns_servers), dnsServers) {
            OutlinedTextField(dnsServers, { dnsServers = it }, label = { Text(stringResource(R.string.dns_servers)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(
                label = stringResource(R.string.apply_dns),
                onClick = { pendingCommand = PendingSafeCommand("dns.set_servers", JSONObject().put("servers", dnsServers), genericCommandQueued) },
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["qos.sqm"] == true) {
        ExpandableSettingsCard(stringResource(R.string.sqm_title), stringResource(R.string.sqm_summary)) {
            SwitchSettingRow(stringResource(R.string.sqm_enabled), checked = sqmEnabled, onCheckedChange = { sqmEnabled = it })
            OptionSelector(stringResource(R.string.sqm_interface), sqmInterface, interfaceOptions, { sqmInterface = it })
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(sqmDownload, { sqmDownload = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.download_limit)) }, modifier = Modifier.weight(1f), singleLine = true)
                OutlinedTextField(sqmUpload, { sqmUpload = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.upload_limit)) }, modifier = Modifier.weight(1f), singleLine = true)
            }
            PrimaryActionButton(
                label = stringResource(R.string.apply_sqm),
                onClick = { pendingCommand = PendingSafeCommand("qos.set_sqm", JSONObject().put("enabled", sqmEnabled).put("interface", sqmInterface).put("download_kbps", sqmDownload).put("upload_kbps", sqmUpload), genericCommandQueued) },
                enabled = sqmInterface.isNotBlank() && sqmDownload.isNotBlank() && sqmUpload.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["firewall.port_forward"] == true) {
        ExpandableSettingsCard(stringResource(R.string.port_forwarding), stringResource(R.string.port_forward_summary)) {
            OutlinedTextField(forwardName, { forwardName = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(forwardExternalPort, { forwardExternalPort = it }, label = { Text(stringResource(R.string.external_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(forwardInternalIp, { forwardInternalIp = it }, label = { Text(stringResource(R.string.internal_ip)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(forwardInternalPort, { forwardInternalPort = it }, label = { Text(stringResource(R.string.internal_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow {
                PrimaryActionButton(
                    label = stringResource(R.string.add_port_forward),
                    onClick = { pendingCommand = PendingSafeCommand("firewall.set_port_forward", JSONObject().put("name", forwardName).put("protocol", "tcp").put("external_port", forwardExternalPort).put("internal_ip", forwardInternalIp).put("internal_port", forwardInternalPort), genericCommandQueued) },
                    enabled = forwardName.isNotBlank() && forwardExternalPort.isNotBlank() && forwardInternalIp.isNotBlank() && forwardInternalPort.isNotBlank(),
                )
                TextButton(onClick = { pendingCommand = PendingSafeCommand("firewall.delete_port_forward", JSONObject().put("name", forwardName), genericCommandQueued) }, enabled = forwardName.isNotBlank()) {
                    Text(stringResource(R.string.delete_port_forward))
                }
            }
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["network.ipv6.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.ipv6_settings), "/$ipv6Prefix") {
            SwitchSettingRow(stringResource(R.string.ipv6_settings), checked = ipv6Enabled, onCheckedChange = { ipv6Enabled = it })
            OptionSelector(stringResource(R.string.prefix_length), ipv6Prefix, ipv6PrefixOptions, { ipv6Prefix = it })
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("network.set_ipv6", JSONObject().put("interface", "lan").put("enabled", ipv6Enabled).put("assignment_length", ipv6Prefix.toIntOrNull() ?: 64).put("ra", "server").put("dhcpv6", "server").put("ndp", "server"), genericCommandQueued) }, Modifier.align(Alignment.End))
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["network.multiwan.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.multiwan_settings), "$primaryWan → $secondaryWan") {
            SwitchSettingRow(stringResource(R.string.multiwan_settings), checked = multiWanEnabled, onCheckedChange = { multiWanEnabled = it })
            OptionSelector(stringResource(R.string.primary_wan), primaryWan, interfaceOptions, { primaryWan = it })
            OptionSelector(stringResource(R.string.secondary_wan), secondaryWan, interfaceOptions, { secondaryWan = it })
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("network.set_multiwan", JSONObject().put("enabled", multiWanEnabled).put("primary_interface", primaryWan).put("secondary_interface", secondaryWan).put("primary_metric", 10).put("secondary_metric", 20), genericCommandQueued) }, Modifier.align(Alignment.End))
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["network.routes.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.static_routes), routeTarget) {
            OutlinedTextField(routeName, { routeName = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(routeTarget, { routeTarget = it }, label = { Text(stringResource(R.string.route_target)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(routeGateway, { routeGateway = it }, label = { Text(stringResource(R.string.gateway)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(routeMetric, { routeMetric = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.route_metric)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow { PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("network.set_route", JSONObject().put("name", routeName).put("interface", "wan").put("target", routeTarget).put("gateway", routeGateway).put("metric", routeMetric.toIntOrNull() ?: 0), genericCommandQueued) }, enabled = routeName.isNotBlank() && routeTarget.isNotBlank()); TextButton({ pendingCommand = PendingSafeCommand("network.delete_route", JSONObject().put("name", routeName), genericCommandQueued) }, enabled = routeName.isNotBlank()) { Text(stringResource(R.string.delete)) } }
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["network.ddns.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.ddns_settings), ddnsDomain) {
            OutlinedTextField(ddnsName, { ddnsName = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ddnsProvider, { ddnsProvider = it }, label = { Text(stringResource(R.string.provider)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ddnsDomain, { ddnsDomain = it }, label = { Text(stringResource(R.string.domain)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ddnsUser, { ddnsUser = it }, label = { Text(stringResource(R.string.username)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ddnsPassword, { ddnsPassword = it }, label = { Text(stringResource(R.string.password)) }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("network.set_ddns", JSONObject().put("name", ddnsName).put("enabled", true).put("provider", ddnsProvider).put("domain", ddnsDomain).put("username", ddnsUser).put("password", ddnsPassword).put("interface", "wan"), genericCommandQueued) }, Modifier.align(Alignment.End), enabled = ddnsDomain.isNotBlank())
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["firewall.upnp.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.upnp_settings), if (upnpEnabled) stringResource(R.string.enabled_value) else stringResource(R.string.disabled_value)) {
            SwitchSettingRow(stringResource(R.string.upnp_settings), checked = upnpEnabled, onCheckedChange = { upnpEnabled = it })
            SwitchSettingRow(stringResource(R.string.secure_mode), checked = upnpSecure, onCheckedChange = { upnpSecure = it })
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("network.set_upnp", JSONObject().put("enabled", upnpEnabled).put("secure_mode", upnpSecure), genericCommandQueued) }, Modifier.align(Alignment.End))
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["firewall.zones.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.firewall_zone), zoneNameValue) {
            OutlinedTextField(zoneNameValue, { zoneNameValue = it }, label = { Text(stringResource(R.string.firewall_zone)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(zoneNetworks, { zoneNetworks = it }, label = { Text(stringResource(R.string.zone_networks)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("firewall.set_zone", JSONObject().put("name", zoneNameValue).put("networks", JSONArray(zoneNetworks.split(' ').filter(String::isNotBlank))).put("input", "REJECT").put("output", "ACCEPT").put("forward", "REJECT").put("masquerade", false), genericCommandQueued) }, Modifier.align(Alignment.End), enabled = zoneNameValue.isNotBlank() && zoneNetworks.isNotBlank())
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["firewall.rules.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.firewall_rule), ruleNameValue) {
            OutlinedTextField(ruleNameValue, { ruleNameValue = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OptionSelector(stringResource(R.string.source_zone), ruleSource, firewallZoneOptions, { ruleSource = it })
            OptionSelector(stringResource(R.string.destination_zone), ruleDestination, firewallZoneOptions, { ruleDestination = it })
            OutlinedTextField(rulePort, { rulePort = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.internal_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow { PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("firewall.set_rule", JSONObject().put("name", ruleNameValue).put("src", ruleSource).put("dest", ruleDestination).put("protocol", "tcpudp").put("dest_port", rulePort).put("target", "ACCEPT"), genericCommandQueued) }, enabled = ruleNameValue.isNotBlank()); TextButton({ pendingCommand = PendingSafeCommand("firewall.delete_rule", JSONObject().put("name", ruleNameValue), genericCommandQueued) }, enabled = ruleNameValue.isNotBlank()) { Text(stringResource(R.string.delete)) } }
        }
    }
    if (mode == NetworkScreenMode.Vpn && capabilities["vpn.wireguard.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.wireguard_interface), wgName) {
            OutlinedTextField(wgName, { wgName = it }, label = { Text(stringResource(R.string.interface_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgAddress, { wgAddress = it }, label = { Text(stringResource(R.string.tunnel_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPort, { wgPort = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.listen_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPrivateKey, { wgPrivateKey = it }, label = { Text(stringResource(R.string.private_key_optional)) }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("vpn.wireguard.set_interface", JSONObject().put("name", wgName).put("enabled", true).put("mode", "server").put("addresses", JSONArray(listOf(wgAddress))).put("listen_port", wgPort.toIntOrNull() ?: 51820).put("private_key", wgPrivateKey).put("mtu", 1420), genericCommandQueued) }, Modifier.align(Alignment.End), enabled = wgName.isNotBlank() && wgAddress.isNotBlank())
        }
        ExpandableSettingsCard(stringResource(R.string.wireguard_peer), wgPeerName) {
            OutlinedTextField(wgName, { wgName = it }, label = { Text(stringResource(R.string.interface_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerName, { wgPeerName = it }, label = { Text(stringResource(R.string.peer_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerPublicKey, { wgPeerPublicKey = it }, label = { Text(stringResource(R.string.public_key)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerPresharedKey, { wgPeerPresharedKey = it }, label = { Text(stringResource(R.string.preshared_key_optional)) }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerAllowedIps, { wgPeerAllowedIps = it }, label = { Text(stringResource(R.string.allowed_ips)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerEndpoint, { wgPeerEndpoint = it }, label = { Text(stringResource(R.string.endpoint_optional)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("vpn.wireguard.set_peer", JSONObject().put("interface", wgName).put("name", wgPeerName).put("public_key", wgPeerPublicKey).put("preshared_key", wgPeerPresharedKey).put("allowed_ips", JSONArray(listOf(wgPeerAllowedIps))).put("endpoint", wgPeerEndpoint).put("persistent_keepalive", 25).put("route_allowed_ips", true), genericCommandQueued) }, Modifier.align(Alignment.End), enabled = wgPeerName.isNotBlank() && wgPeerPublicKey.isNotBlank())
            ActionRow {
                TextButton({ pendingCommand = PendingSafeCommand("vpn.wireguard.export_peer", JSONObject().put("interface", wgName).put("name", wgPeerName), genericCommandQueued) }, enabled = wgPeerName.isNotBlank()) { Text(stringResource(R.string.export)) }
                TextButton({ pendingCommand = PendingSafeCommand("vpn.wireguard.delete_peer", JSONObject().put("interface", wgName).put("name", wgPeerName), genericCommandQueued) }, enabled = wgPeerName.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
    }
    if (mode == NetworkScreenMode.Vpn && capabilities["vpn.openvpn.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.openvpn_client), openVpnName) {
            OutlinedTextField(openVpnName, { openVpnName = it }, label = { Text(stringResource(R.string.profile_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(openVpnConfig, { openVpnConfig = it }, label = { Text(stringResource(R.string.openvpn_config)) }, modifier = Modifier.fillMaxWidth(), minLines = 6)
            ActionRow {
                PrimaryActionButton(stringResource(R.string.import_profile), { pendingCommand = PendingSafeCommand("vpn.openvpn.set_client", JSONObject().put("name", openVpnName).put("enabled", true).put("config", openVpnConfig), genericCommandQueued) }, enabled = openVpnName.isNotBlank() && openVpnConfig.isNotBlank())
                TextButton({ pendingCommand = PendingSafeCommand("vpn.openvpn.delete_client", JSONObject().put("name", openVpnName), genericCommandQueued) }, enabled = openVpnName.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
    }
    if (mode == NetworkScreenMode.Vpn && capabilities["vpn.policy.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.policy_routing), vpnPolicyName) {
            OutlinedTextField(vpnPolicyName, { vpnPolicyName = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(vpnPolicyInterface, { vpnPolicyInterface = it }, label = { Text(stringResource(R.string.vpn_interface)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(vpnPolicySource, { vpnPolicySource = it }, label = { Text(stringResource(R.string.policy_source)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(vpnPolicyDestination, { vpnPolicyDestination = it }, label = { Text(stringResource(R.string.policy_destination)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow {
                PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("vpn.policy.set", JSONObject().put("name", vpnPolicyName).put("enabled", true).put("interface", vpnPolicyInterface).put("source", vpnPolicySource).put("destination", vpnPolicyDestination).put("protocol", "all"), genericCommandQueued) }, enabled = vpnPolicyName.isNotBlank() && vpnPolicyInterface.isNotBlank() && (vpnPolicySource.isNotBlank() || vpnPolicyDestination.isNotBlank()))
                TextButton({ pendingCommand = PendingSafeCommand("vpn.policy.delete", JSONObject().put("name", vpnPolicyName), genericCommandQueued) }, enabled = vpnPolicyName.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
    }
    if (mode == NetworkScreenMode.Internet && (capabilities["network.interface_restart"] == true || capabilities["network.restart"] == true)) {
        ExpandableSettingsCard(stringResource(R.string.network_maintenance), stringResource(R.string.network_maintenance_summary)) {
            if (capabilities["network.interface_restart"] == true) {
                OptionSelector(stringResource(R.string.network_interfaces), interfaceName, interfaceOptions, { interfaceName = it })
                SecondaryActionButton(
                    label = stringResource(R.string.restart_interface),
                    onClick = { pendingCommand = PendingSafeCommand("network.interface_restart", JSONObject().put("interface", interfaceName), interfaceRestartQueued) },
                    enabled = interfaceName.isNotBlank(),
                    modifier = Modifier.align(Alignment.End),
                )
            }
            if (capabilities["network.restart"] == true) {
                SecondaryActionButton(
                    stringResource(R.string.restart_network),
                    { pendingCommand = PendingSafeCommand("network.restart", JSONObject(), networkRestartQueued) },
                    Modifier.align(Alignment.End),
                )
            }
        }
    }
    MessageBanner(message, error = messageIsError)
    pendingCommand?.let { command -> SafeCommandDialog(
        serverUrl, accessToken, device.id, command,
        onDismiss = { pendingCommand = null },
        onApply = {
            pendingCommand = null
            queue(command.type, command.payload, command.successMessage)
        },
        onSessionExpired = onSessionExpired,
    ) }
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
    var zoneName by remember { mutableStateOf("") }
    var timezoneValue by remember { mutableStateOf("") }
    var ntpEnabled by remember { mutableStateOf(false) }
    var ntpServers by remember { mutableStateOf("") }
    var packageName by remember { mutableStateOf("") }
    var backupArchive by remember { mutableStateOf("") }
    var firmwareUrl by remember { mutableStateOf("") }
    var firmwareSha256 by remember { mutableStateOf("") }
    var logLines by remember { mutableStateOf("100") }
    var processPid by remember { mutableStateOf("") }
    var processSignal by remember { mutableStateOf("TERM") }
    var cronContent by remember { mutableStateOf("") }
    var pendingSystemCommand by remember { mutableStateOf<PendingSafeCommand?>(null) }
    var formInitialized by remember(device.id) { mutableStateOf(false) }
    val refresh: () -> Unit = {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(device.id) }) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    hostnameValue = result.data.system?.optString("hostname").orEmpty().ifBlank { device.hostname }
                    if (!formInitialized) {
                        val time = result.data.system
                        zoneName = time?.optString("zonename").orEmpty()
                        timezoneValue = time?.optString("timezone").orEmpty()
                        ntpEnabled = time?.optBoolean("ntp_enabled", false) ?: false
                        ntpServers = time?.optJSONArray("ntp_servers")?.let { array ->
                            (0 until array.length()).joinToString(", ") { array.optString(it) }
                        }.orEmpty()
                        formInitialized = true
                    }
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
            PrimaryActionButton(
                label = stringResource(R.string.change_hostname),
                onClick = { pendingSystemCommand = PendingSafeCommand("system.set_hostname", JSONObject().put("hostname", hostnameValue), hostnameQueued) },
                enabled = hostnameValue.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (capabilities["system.set_timezone"] == true || capabilities["system.set_ntp"] == true) {
        ExpandableSettingsCard(stringResource(R.string.time_settings), zoneName) {
            if (capabilities["system.set_timezone"] == true) {
                OptionSelector(
                    stringResource(R.string.timezone_region),
                    zoneName,
                    timezoneOptions.map { SelectOption(it.zonename, it.label) },
                    {
                        zoneName = it
                        timezoneValue = timezoneOptions.firstOrNull { option -> option.zonename == it }?.timezone.orEmpty()
                    },
                )
                PrimaryActionButton(
                    label = stringResource(R.string.save_time_settings),
                    onClick = { pendingSystemCommand = PendingSafeCommand("system.set_timezone", JSONObject().put("zonename", zoneName).put("timezone", timezoneValue), systemCommandQueued) },
                    modifier = Modifier.align(Alignment.End),
                )
            }
            if (capabilities["system.set_ntp"] == true) {
                HorizontalDivider()
                SwitchSettingRow(
                    stringResource(R.string.ntp_sync),
                    checked = ntpEnabled,
                    onCheckedChange = { ntpEnabled = it },
                )
                OutlinedTextField(ntpServers, { ntpServers = it }, label = { Text(stringResource(R.string.ntp_servers)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                PrimaryActionButton(
                    label = stringResource(R.string.apply_ntp),
                    onClick = { pendingSystemCommand = PendingSafeCommand("system.set_ntp", JSONObject().put("enabled", ntpEnabled).put("servers", ntpServers), systemCommandQueued) },
                    enabled = !ntpEnabled || ntpServers.isNotBlank(),
                    modifier = Modifier.align(Alignment.End),
                )
            }
        }
    }
    if (capabilities["system.restart_service"] == true) {
        ExpandableSettingsCard(stringResource(R.string.service_management), stringResource(R.string.service_management_summary)) {
            listOf("dnsmasq", "firewall", "odhcpd", "network").forEach { service ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(service, modifier = Modifier.weight(1f))
                    TextButton(onClick = { pendingSystemCommand = PendingSafeCommand("system.restart_service", JSONObject().put("service", service), serviceQueued) }) {
                        Text(stringResource(R.string.restart_service))
                    }
                }
            }
        }
    }
    if (capabilities["maintenance.packages.read"] == true || capabilities["maintenance.packages.write"] == true) {
        ExpandableSettingsCard(stringResource(R.string.router_packages), stringResource(R.string.router_packages_summary)) {
            if (capabilities["maintenance.packages.read"] == true) {
                TonalActionButton(stringResource(R.string.refresh_package_catalog), { pendingSystemCommand = PendingSafeCommand("maintenance.packages.refresh", JSONObject(), systemCommandQueued) })
            }
            if (capabilities["maintenance.packages.write"] == true) {
                OutlinedTextField(packageName, { packageName = it }, label = { Text(stringResource(R.string.package_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                ActionRow {
                    PrimaryActionButton(stringResource(R.string.install_package), { pendingSystemCommand = PendingSafeCommand("maintenance.package.install", JSONObject().put("package", packageName), systemCommandQueued) }, enabled = packageName.isNotBlank())
                    TextButton({ pendingSystemCommand = PendingSafeCommand("maintenance.package.remove", JSONObject().put("package", packageName), systemCommandQueued) }, enabled = packageName.isNotBlank()) { Text(stringResource(R.string.remove_package)) }
                }
            }
        }
    }
    if (capabilities["maintenance.backup"] == true) {
        ExpandableSettingsCard(stringResource(R.string.configuration_backup), stringResource(R.string.configuration_backup_summary)) {
            TonalActionButton(stringResource(R.string.create_backup), { pendingSystemCommand = PendingSafeCommand("maintenance.backup.create", JSONObject(), systemCommandQueued) })
            OutlinedTextField(backupArchive, { backupArchive = it }, label = { Text(stringResource(R.string.backup_base64)) }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            SecondaryActionButton(stringResource(R.string.restore_backup), { pendingSystemCommand = PendingSafeCommand("maintenance.backup.restore", JSONObject().put("archive_base64", backupArchive), systemCommandQueued) }, enabled = backupArchive.isNotBlank())
        }
    }
    if (capabilities["maintenance.sysupgrade.check"] == true) {
        ExpandableSettingsCard(stringResource(R.string.openwrt_update), stringResource(R.string.openwrt_update_summary)) {
            OutlinedTextField(firmwareUrl, { firmwareUrl = it }, label = { Text(stringResource(R.string.firmware_url)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(firmwareSha256, { firmwareSha256 = it }, label = { Text("SHA-256") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(stringResource(R.string.validate_firmware), { pendingSystemCommand = PendingSafeCommand("maintenance.sysupgrade.check", JSONObject().put("url", firmwareUrl).put("sha256", firmwareSha256).put("expected_model", "").put("preserve_config", true), systemCommandQueued) }, enabled = firmwareUrl.startsWith("https://") && firmwareSha256.length == 64)
            if (capabilities["maintenance.sysupgrade.apply"] == true) {
                SecondaryActionButton(stringResource(R.string.install_validated_firmware), { pendingSystemCommand = PendingSafeCommand("maintenance.sysupgrade.apply", JSONObject().put("sha256", firmwareSha256).put("preserve_config", true), systemCommandQueued) }, enabled = firmwareSha256.length == 64)
            }
        }
    }
    if (capabilities["maintenance.logs"] == true || capabilities["maintenance.processes"] == true || capabilities["maintenance.cron"] == true) {
        ExpandableSettingsCard(stringResource(R.string.advanced_maintenance), stringResource(R.string.advanced_maintenance_summary)) {
            if (capabilities["maintenance.logs"] == true) {
                OutlinedTextField(logLines, { logLines = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.log_lines)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                TonalActionButton(stringResource(R.string.request_logs), { pendingSystemCommand = PendingSafeCommand("maintenance.logs.read", JSONObject().put("lines", logLines.toIntOrNull() ?: 100), systemCommandQueued) })
            }
            if (capabilities["maintenance.processes"] == true) {
                OutlinedTextField(processPid, { processPid = it.filter(Char::isDigit) }, label = { Text("PID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OptionSelector("Signal", processSignal, processSignalOptions, { processSignal = it })
                SecondaryActionButton(stringResource(R.string.terminate_process), { pendingSystemCommand = PendingSafeCommand("maintenance.process.signal", JSONObject().put("pid", processPid.toIntOrNull() ?: 0).put("signal", processSignal), systemCommandQueued) }, enabled = (processPid.toIntOrNull() ?: 0) > 1)
            }
            if (capabilities["maintenance.cron"] == true) {
                OutlinedTextField(cronContent, { cronContent = it }, label = { Text(stringResource(R.string.root_crontab)) }, modifier = Modifier.fillMaxWidth(), minLines = 3)
                SecondaryActionButton(stringResource(R.string.save_schedule), { pendingSystemCommand = PendingSafeCommand("maintenance.cron.set", JSONObject().put("content", cronContent), systemCommandQueued) })
            }
        }
    }
    if (capabilities["maintenance.diagnostics.bundle"] == true || capabilities["maintenance.recovery"] == true) {
        ExpandableSettingsCard(stringResource(R.string.recovery_tools), stringResource(R.string.recovery_tools_summary)) {
            if (capabilities["maintenance.diagnostics.bundle"] == true) TonalActionButton(stringResource(R.string.create_diagnostic_bundle), { pendingSystemCommand = PendingSafeCommand("maintenance.diagnostics.bundle", JSONObject(), systemCommandQueued) })
            if (capabilities["maintenance.recovery"] == true) ActionRow {
                SecondaryActionButton(stringResource(R.string.enable_recovery_mode), { pendingSystemCommand = PendingSafeCommand("maintenance.recovery.enable", JSONObject(), systemCommandQueued) })
                TextButton({ pendingSystemCommand = PendingSafeCommand("maintenance.recovery.disable", JSONObject(), systemCommandQueued) }) { Text(stringResource(R.string.disable_recovery_mode)) }
            }
        }
    }
    SectionCard(stringResource(R.string.system_actions), subtitle = stringResource(R.string.system_actions_summary)) {
        ActionRow {
            if (capabilities["diagnostics.check_server"] == true) {
                TonalActionButton(
                    label = stringResource(R.string.diagnostics),
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
                )
            }
            if (capabilities["system.reboot"] == true) {
                SecondaryActionButton(stringResource(R.string.reboot), { confirmReboot = true })
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
    pendingSystemCommand?.let { command -> SafeCommandDialog(
        serverUrl, accessToken, device.id, command,
        onDismiss = { pendingSystemCommand = null },
        onApply = {
            pendingSystemCommand = null
            queueSystem(command.type, command.payload, command.successMessage)
        },
        onSessionExpired = onSessionExpired,
    ) }
}

private fun firstRadio(telemetry: TelemetryDto?): JSONObject? =
    telemetry?.wifi?.optJSONArray("radios")?.optJSONObject(0)
        ?: telemetry?.payload?.optJSONObject("wifi")?.optJSONArray("radios")?.optJSONObject(0)

private fun firstInterface(telemetry: TelemetryDto?): JSONObject? =
    firstRadio(telemetry)?.optJSONArray("interfaces")?.optJSONObject(0)

private fun findRadio(radios: JSONArray, radioId: String): JSONObject? =
    (0 until radios.length()).mapNotNull(radios::optJSONObject)
        .firstOrNull { it.optString("id") == radioId }

private fun findInterface(interfaces: JSONArray, interfaceId: String): JSONObject? =
    (0 until interfaces.length()).mapNotNull(interfaces::optJSONObject)
        .firstOrNull { it.optString("id") == interfaceId }

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
