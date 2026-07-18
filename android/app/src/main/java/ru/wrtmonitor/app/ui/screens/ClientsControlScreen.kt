package ru.wrtmonitor.app.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.DevicesOther
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material.icons.filled.Router
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.ClientProfileDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.NetworkClientDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.ui.components.ActionRow
import ru.wrtmonitor.app.ui.components.ExpandableSettingsCard
import ru.wrtmonitor.app.ui.components.InfoRow
import ru.wrtmonitor.app.ui.components.MessageBanner
import ru.wrtmonitor.app.ui.components.MultiOptionSelector
import ru.wrtmonitor.app.ui.components.OptionSelector
import ru.wrtmonitor.app.ui.components.PrimaryActionButton
import ru.wrtmonitor.app.ui.components.RouterPageHeader
import ru.wrtmonitor.app.ui.components.SectionCard
import ru.wrtmonitor.app.ui.components.SelectOption
import ru.wrtmonitor.app.ui.components.StatusPill
import ru.wrtmonitor.app.ui.components.SwitchSettingRow
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

private enum class ClientsView { List, Details, Settings }

private enum class ClientsFilter { All, Online, Offline }

private val clientWeekdayOptions = listOf("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    .map { SelectOption(it, it.uppercase()) }
private val clientPriorityOptions = listOf("low", "normal", "high", "realtime")
    .map { SelectOption(it, it) }
private val clientLeaseTimeOptions = listOf("30m", "1h", "6h", "12h", "24h", "72h", "168h")
    .map { SelectOption(it, it) }

@Composable
fun ClientsControlScreen(
    serverUrl: String,
    accessToken: String,
    device: DeviceDto,
    onSessionExpired: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var telemetry by remember(device.id) { mutableStateOf<TelemetryDto?>(null) }
    var clients by remember(device.id) { mutableStateOf<List<NetworkClientDto>>(emptyList()) }
    var profiles by remember(device.id) { mutableStateOf<List<ClientProfileDto>>(emptyList()) }
    var view by remember(device.id) { mutableStateOf(ClientsView.List) }
    var selectedClientId by remember(device.id) { mutableStateOf<String?>(null) }
    var search by remember(device.id) { mutableStateOf("") }
    var filter by remember(device.id) { mutableStateOf(ClientsFilter.All) }
    var profileName by remember(device.id) { mutableStateOf("") }
    var profileBlocked by remember(device.id) { mutableStateOf(false) }
    var poolStart by remember(device.id) { mutableStateOf("") }
    var poolLimit by remember(device.id) { mutableStateOf("") }
    var leaseTime by remember(device.id) { mutableStateOf("") }
    var dhcpInitialized by remember(device.id) { mutableStateOf(false) }
    var loading by remember(device.id) { mutableStateOf(false) }
    var message by remember(device.id) { mutableStateOf("") }
    var messageIsError by remember(device.id) { mutableStateOf(false) }
    var pendingCommand by remember(device.id) { mutableStateOf<PendingSafeCommand?>(null) }
    val commandQueued = stringResource(R.string.command_queued)
    val leaseQueued = stringResource(R.string.lease_queued)

    val refresh: () -> Unit = {
        scope.launch {
            loading = true
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
                is ApiResult.Success -> clients = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            when (val result = withContext(Dispatchers.IO) { api.getClientProfiles(device.id) }) {
                is ApiResult.Success -> profiles = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            loading = false
        }
    }

    fun queue(type: String, payload: JSONObject) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) {
                WrtMonitorApi(serverUrl, accessToken).createCommand(device.id, type, payload, true)
            }) {
                is ApiResult.Success -> {
                    message = if (type.startsWith("dhcp.")) leaseQueued else commandQueued
                    messageIsError = false
                    refresh()
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
        }
    }

    fun saveClient(client: NetworkClientDto, name: String, profileId: String?, policy: JSONObject) {
        scope.launch {
            val api = WrtMonitorApi(serverUrl, accessToken)
            val storedPolicy = if (profileId == null) policy else JSONObject()
            when (val update = withContext(Dispatchers.IO) {
                api.updateNetworkClient(device.id, client.id, name, profileId, storedPolicy)
            }) {
                is ApiResult.Success -> when (val apply = withContext(Dispatchers.IO) {
                    api.applyNetworkClientPolicy(device.id, client.id)
                }) {
                    is ApiResult.Success -> {
                        message = commandQueued
                        messageIsError = false
                        refresh()
                    }
                    is ApiResult.Error -> if (apply.isUnauthorized()) onSessionExpired() else {
                        message = apply.message
                        messageIsError = true
                    }
                }
                is ApiResult.Error -> if (update.isUnauthorized()) onSessionExpired() else {
                    message = update.message
                    messageIsError = true
                }
            }
        }
    }

    LaunchedEffect(device.id) { refresh() }
    BackHandler(view != ClientsView.List) {
        view = ClientsView.List
        selectedClientId = null
    }

    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()
    val selectedClient = clients.firstOrNull { it.id == selectedClientId }
    when {
        view == ClientsView.Details && selectedClient != null -> ClientDetails(
            client = selectedClient,
            profiles = profiles,
            canManagePolicy = capabilities["clients.policy"] == true,
            canSetLease = capabilities["dhcp.set_lease"] == true,
            canDeleteLease = capabilities["dhcp.delete_lease"] == true,
            onBack = {
                view = ClientsView.List
                selectedClientId = null
            },
            onSave = { name, profileId, policy -> saveClient(selectedClient, name, profileId, policy) },
            onSetLease = { hostname, ip ->
                pendingCommand = PendingSafeCommand(
                    "dhcp.set_lease",
                    JSONObject().put("hostname", hostname).put("mac", selectedClient.mac).put("ip", ip),
                    leaseQueued,
                )
            },
            onDeleteLease = {
                pendingCommand = PendingSafeCommand(
                    "dhcp.delete_lease",
                    JSONObject().put("mac", selectedClient.mac),
                    commandQueued,
                )
            },
        )
        view == ClientsView.Settings -> ClientsSettings(
            profiles = profiles,
            canManageProfiles = capabilities["clients.policy"] == true,
            canConfigureDhcp = capabilities["dhcp.configure"] == true,
            profileName = profileName,
            onProfileNameChange = { profileName = it },
            profileBlocked = profileBlocked,
            onProfileBlockedChange = { profileBlocked = it },
            poolStart = poolStart,
            onPoolStartChange = { poolStart = it.filter(Char::isDigit) },
            poolLimit = poolLimit,
            onPoolLimitChange = { poolLimit = it.filter(Char::isDigit) },
            leaseTime = leaseTime,
            onLeaseTimeChange = { leaseTime = it },
            onBack = { view = ClientsView.List },
            onCreateProfile = {
                scope.launch {
                    when (val result = withContext(Dispatchers.IO) {
                        WrtMonitorApi(serverUrl, accessToken).createClientProfile(device.id, profileName, profileBlocked)
                    }) {
                        is ApiResult.Success -> {
                            profileName = ""
                            profileBlocked = false
                            refresh()
                        }
                        is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                            message = result.message
                            messageIsError = true
                        }
                    }
                }
            },
            onDeleteProfile = { profileId ->
                scope.launch {
                    when (val result = withContext(Dispatchers.IO) {
                        WrtMonitorApi(serverUrl, accessToken).deleteClientProfile(device.id, profileId)
                    }) {
                        is ApiResult.Success -> refresh()
                        is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                            message = result.message
                            messageIsError = true
                        }
                    }
                }
            },
            onSaveDhcp = {
                pendingCommand = PendingSafeCommand(
                    "dhcp.set_pool",
                    JSONObject().put("interface", "lan").put("start", poolStart)
                        .put("limit", poolLimit).put("leasetime", leaseTime),
                    commandQueued,
                )
            },
        )
        else -> ClientsList(
            clients = clients,
            search = search,
            onSearchChange = { search = it },
            filter = filter,
            onFilterChange = { filter = it },
            loading = loading,
            onRefresh = refresh,
            onOpenSettings = { view = ClientsView.Settings },
            onOpenClient = {
                selectedClientId = it.id
                view = ClientsView.Details
            },
        )
    }
    MessageBanner(message, error = messageIsError)

    pendingCommand?.let { command ->
        SafeCommandDialog(
            serverUrl = serverUrl,
            accessToken = accessToken,
            deviceId = device.id,
            command = command,
            onDismiss = { pendingCommand = null },
            onApply = {
                pendingCommand = null
                queue(command.type, command.payload)
            },
            onSessionExpired = onSessionExpired,
        )
    }
}

@Composable
private fun ClientsList(
    clients: List<NetworkClientDto>,
    search: String,
    onSearchChange: (String) -> Unit,
    filter: ClientsFilter,
    onFilterChange: (ClientsFilter) -> Unit,
    loading: Boolean,
    onRefresh: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenClient: (NetworkClientDto) -> Unit,
) {
    val onlineCount = clients.count(NetworkClientDto::online)
    val query = search.trim().lowercase(Locale.getDefault())
    val filtered = clients.filter { client ->
        val stateMatches = when (filter) {
            ClientsFilter.All -> true
            ClientsFilter.Online -> client.online
            ClientsFilter.Offline -> !client.online
        }
        val searchable = listOfNotNull(
            client.displayName,
            client.hostname,
            client.vendor,
            client.currentIpv4,
            client.mac,
            client.wifiSsid,
        ).joinToString(" ").lowercase(Locale.getDefault())
        stateMatches && (query.isBlank() || query in searchable)
    }

    RouterPageHeader(
        title = stringResource(R.string.clients_title_count, clients.size),
        subtitle = stringResource(R.string.clients_online_count, onlineCount),
        refreshing = loading,
        onRefresh = onRefresh,
    )
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        TextButton(onClick = onOpenSettings) {
            Icon(Icons.Default.Settings, contentDescription = null, modifier = Modifier.size(18.dp))
            Text(stringResource(R.string.client_list_settings), Modifier.padding(start = 6.dp))
        }
    }
    OutlinedTextField(
        value = search,
        onValueChange = onSearchChange,
        modifier = Modifier.fillMaxWidth(),
        leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
        placeholder = { Text(stringResource(R.string.client_search_hint)) },
        singleLine = true,
    )
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(
            selected = filter == ClientsFilter.All,
            onClick = { onFilterChange(ClientsFilter.All) },
            modifier = Modifier.weight(1f),
            label = { Text(stringResource(R.string.client_filter_all, clients.size), maxLines = 1, overflow = TextOverflow.Ellipsis) },
        )
        FilterChip(
            selected = filter == ClientsFilter.Online,
            onClick = { onFilterChange(ClientsFilter.Online) },
            modifier = Modifier.weight(1f),
            label = { Text(stringResource(R.string.client_filter_online, onlineCount), maxLines = 1, overflow = TextOverflow.Ellipsis) },
        )
        FilterChip(
            selected = filter == ClientsFilter.Offline,
            onClick = { onFilterChange(ClientsFilter.Offline) },
            modifier = Modifier.weight(1f),
            label = { Text(stringResource(R.string.client_filter_offline, clients.size - onlineCount), maxLines = 1, overflow = TextOverflow.Ellipsis) },
        )
    }

    if (filtered.isEmpty()) {
        SectionCard(stringResource(R.string.home_network_clients)) {
            Text(stringResource(R.string.client_filter_empty), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }

    val groups = filtered.groupBy(::clientGroupKey).toList().sortedWith(
        compareBy<Pair<String, List<NetworkClientDto>>> { if (it.first == "offline") 1 else 0 }
            .thenBy { it.first.lowercase(Locale.getDefault()) },
    )
    groups.forEach { (key, groupClients) ->
        ClientGroup(
            title = clientGroupTitle(key, groupClients),
            subtitle = clientGroupSubtitle(groupClients),
            initiallyExpanded = key != "offline",
            forceExpanded = query.isNotBlank() || filter != ClientsFilter.All,
            clients = groupClients.sortedWith(
                compareByDescending<NetworkClientDto> { it.online }
                    .thenBy { clientDisplayNameRaw(it).lowercase(Locale.getDefault()) },
            ),
            onOpenClient = onOpenClient,
        )
    }
}

@Composable
private fun ClientGroup(
    title: String,
    subtitle: String,
    initiallyExpanded: Boolean,
    forceExpanded: Boolean,
    clients: List<NetworkClientDto>,
    onOpenClient: (NetworkClientDto) -> Unit,
) {
    var expanded by remember(title) { mutableStateOf(initiallyExpanded) }
    LaunchedEffect(forceExpanded) {
        if (forceExpanded) expanded = true
    }
    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth().clickable { expanded = !expanded }.padding(horizontal = 4.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(
                if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (expanded) {
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.surface,
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
            ) {
                Column {
                    clients.forEachIndexed { index, client ->
                        ClientRow(client, onClick = { onOpenClient(client) })
                        if (index < clients.lastIndex) HorizontalDivider(Modifier.padding(start = 64.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun ClientRow(client: NetworkClientDto, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 14.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(38.dp).background(
                if (client.online) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                CircleShape,
            ),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                clientIcon(client),
                contentDescription = null,
                modifier = Modifier.size(21.dp),
                tint = if (client.online) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.outline,
            )
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                clientDisplayName(client),
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                client.currentIpv4 ?: compactMac(client.mac),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                clientConnectionLabel(client),
                style = MaterialTheme.typography.labelMedium,
                color = if (client.online) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.outline,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (client.staticIpv4 != null) {
                Text("IP", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            }
        }
        Icon(Icons.Default.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.outline)
    }
}

@Composable
private fun ClientDetails(
    client: NetworkClientDto,
    profiles: List<ClientProfileDto>,
    canManagePolicy: Boolean,
    canSetLease: Boolean,
    canDeleteLease: Boolean,
    onBack: () -> Unit,
    onSave: (String, String?, JSONObject) -> Unit,
    onSetLease: (String, String) -> Unit,
    onDeleteLease: () -> Unit,
) {
    val policy = client.effectivePolicy
    val schedule = policy.optJSONObject("schedule") ?: JSONObject()
    val qos = policy.optJSONObject("qos") ?: JSONObject()
    var displayName by remember(client.id, client.displayName) { mutableStateOf(client.displayName.orEmpty()) }
    var profileId by remember(client.id, client.profileId) { mutableStateOf(client.profileId) }
    var blocked by remember(client.id, policy.toString()) { mutableStateOf(policy.optBoolean("blocked")) }
    var scheduleEnabled by remember(client.id, schedule.toString()) { mutableStateOf(schedule.optBoolean("enabled")) }
    var weekdays by remember(client.id, schedule.toString()) {
        mutableStateOf(schedule.optJSONArray("weekdays")?.let { array ->
            (0 until array.length()).map(array::optString).filter(String::isNotBlank).toSet()
        } ?: emptySet())
    }
    var start by remember(client.id, schedule.toString()) { mutableStateOf(schedule.optString("start")) }
    var stop by remember(client.id, schedule.toString()) { mutableStateOf(schedule.optString("stop")) }
    var priority by remember(client.id, qos.toString()) { mutableStateOf(qos.optString("priority", "normal")) }
    var download by remember(client.id, qos.toString()) { mutableStateOf(qos.optInt("download_kbps").toString()) }
    var upload by remember(client.id, qos.toString()) { mutableStateOf(qos.optInt("upload_kbps").toString()) }
    var leaseIp by remember(client.id, client.currentIpv4, client.staticIpv4) {
        mutableStateOf(client.staticIpv4 ?: client.currentIpv4.orEmpty())
    }
    val profileOptions = listOf(SelectOption("", stringResource(R.string.no_profile))) +
        profiles.map { SelectOption(it.id, it.name) }

    ClientBackRow(onBack, stringResource(R.string.back_to_clients))
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier.size(56.dp).background(MaterialTheme.colorScheme.secondaryContainer, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(clientIcon(client), contentDescription = null, modifier = Modifier.size(30.dp), tint = MaterialTheme.colorScheme.secondary)
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(clientDisplayName(client), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
            Text(
                listOfNotNull(client.currentIpv4, compactMac(client.mac)).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        StatusPill(
            if (client.online) stringResource(R.string.online) else stringResource(R.string.offline),
            client.online,
        )
    }

    SectionCard(stringResource(R.string.client_connection_details)) {
        InfoRow(stringResource(R.string.connection_type), clientConnectionLabel(client))
        InfoRow(stringResource(R.string.ip_address), client.currentIpv4, stringResource(R.string.no_ip_address))
        InfoRow(stringResource(R.string.mac_address), client.mac)
        InfoRow(stringResource(R.string.client_vendor), client.vendor, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.client_interface), client.networkInterface, stringResource(R.string.no_data))
        client.signalDbm?.let { InfoRow(stringResource(R.string.client_signal), "$it dBm") }
        val speed = maxOf(client.rxBitrate ?: 0, client.txBitrate ?: 0)
        if (speed > 0) InfoRow(stringResource(R.string.client_link_speed), formatLinkRate(speed))
        InfoRow(stringResource(R.string.first_seen), formatClientDate(client.firstSeenAt), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.last_activity), formatClientDate(client.lastSeenAt), stringResource(R.string.no_data))
    }

    if (canManagePolicy) {
        SectionCard(stringResource(R.string.client_main_settings)) {
            OutlinedTextField(
                value = displayName,
                onValueChange = { displayName = it },
                label = { Text(stringResource(R.string.device_name)) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            OptionSelector(
                stringResource(R.string.client_profile),
                profileId.orEmpty(),
                profileOptions,
                { profileId = it.ifBlank { null } },
            )
            SwitchSettingRow(
                title = stringResource(R.string.block_client),
                subtitle = if (blocked) stringResource(R.string.access_blocked) else stringResource(R.string.access_allowed),
                checked = blocked,
                onCheckedChange = { blocked = it },
            )
        }

        ExpandableSettingsCard(
            stringResource(R.string.client_priority_limits),
            stringResource(R.string.client_priority_summary, priority),
        ) {
            OptionSelector(
                stringResource(R.string.traffic_priority),
                priority,
                clientPriorityOptions,
                { priority = it },
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    download,
                    { download = it.filter(Char::isDigit) },
                    label = { Text(stringResource(R.string.download_limit)) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                )
                OutlinedTextField(
                    upload,
                    { upload = it.filter(Char::isDigit) },
                    label = { Text(stringResource(R.string.upload_limit)) },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                )
            }
        }

        ExpandableSettingsCard(
            stringResource(R.string.access_schedule),
            if (scheduleEnabled) stringResource(R.string.enabled_value) else stringResource(R.string.disabled_value),
        ) {
            SwitchSettingRow(stringResource(R.string.access_schedule), checked = scheduleEnabled, onCheckedChange = { scheduleEnabled = it })
            if (scheduleEnabled) {
                MultiOptionSelector(
                    stringResource(R.string.schedule_weekdays),
                    weekdays,
                    clientWeekdayOptions,
                    { weekdays = it },
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(start, { start = it }, label = { Text(stringResource(R.string.schedule_start)) }, modifier = Modifier.weight(1f), singleLine = true)
                    OutlinedTextField(stop, { stop = it }, label = { Text(stringResource(R.string.schedule_stop)) }, modifier = Modifier.weight(1f), singleLine = true)
                }
            }
        }
    }

    if (canSetLease || (canDeleteLease && client.staticIpv4 != null)) {
        ExpandableSettingsCard(
            stringResource(R.string.static_lease),
            client.staticIpv4 ?: stringResource(R.string.static_lease_missing),
        ) {
            OutlinedTextField(
                value = leaseIp,
                onValueChange = { leaseIp = it },
                label = { Text(stringResource(R.string.ip_address)) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            ActionRow {
                if (canSetLease) {
                    PrimaryActionButton(
                        label = if (client.staticIpv4 == null) stringResource(R.string.pin_current_address) else stringResource(R.string.save_lease),
                        onClick = {
                            onSetLease(
                                displayName.ifBlank { client.hostname ?: "client-${client.mac.takeLast(5).replace(":", "")}" },
                                leaseIp,
                            )
                        },
                        enabled = leaseIp.isNotBlank(),
                    )
                }
                if (canDeleteLease && client.staticIpv4 != null) {
                    TextButton(onClick = onDeleteLease) { Text(stringResource(R.string.delete_lease)) }
                }
            }
        }
    }

    SectionCard(stringResource(R.string.client_traffic)) {
        val traffic = client.traffic
        InfoRow(stringResource(R.string.traffic_received), formatClientBytes(traffic?.optLong("rx_bytes") ?: 0))
        InfoRow(stringResource(R.string.traffic_sent), formatClientBytes(traffic?.optLong("tx_bytes") ?: 0))
    }

    if (canManagePolicy) {
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
        )
    }
}

@Composable
private fun ClientsSettings(
    profiles: List<ClientProfileDto>,
    canManageProfiles: Boolean,
    canConfigureDhcp: Boolean,
    profileName: String,
    onProfileNameChange: (String) -> Unit,
    profileBlocked: Boolean,
    onProfileBlockedChange: (Boolean) -> Unit,
    poolStart: String,
    onPoolStartChange: (String) -> Unit,
    poolLimit: String,
    onPoolLimitChange: (String) -> Unit,
    leaseTime: String,
    onLeaseTimeChange: (String) -> Unit,
    onBack: () -> Unit,
    onCreateProfile: () -> Unit,
    onDeleteProfile: (String) -> Unit,
    onSaveDhcp: () -> Unit,
) {
    ClientBackRow(onBack, stringResource(R.string.back_to_clients))
    RouterPageHeader(
        title = stringResource(R.string.clients_settings_title),
        subtitle = stringResource(R.string.clients_settings_summary),
    )
    if (canManageProfiles) {
        SectionCard(
            title = stringResource(R.string.access_profiles),
            subtitle = stringResource(R.string.profiles_count, profiles.size),
        ) {
            profiles.forEachIndexed { index, profile ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(profile.name, fontWeight = FontWeight.Medium)
                        Text(
                            if (profile.policy.optBoolean("blocked")) stringResource(R.string.access_blocked) else stringResource(R.string.access_allowed),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    TextButton(onClick = { onDeleteProfile(profile.id) }) { Text(stringResource(R.string.delete)) }
                }
                if (index < profiles.lastIndex) HorizontalDivider()
            }
            if (profiles.isNotEmpty()) HorizontalDivider()
            Text(stringResource(R.string.create_profile), style = MaterialTheme.typography.titleSmall)
            OutlinedTextField(
                profileName,
                onProfileNameChange,
                label = { Text(stringResource(R.string.profile_name)) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            SwitchSettingRow(stringResource(R.string.block_client), checked = profileBlocked, onCheckedChange = onProfileBlockedChange)
            PrimaryActionButton(
                label = stringResource(R.string.create_profile),
                onClick = onCreateProfile,
                enabled = profileName.isNotBlank(),
            )
        }
    }
    if (canConfigureDhcp) {
        SectionCard(
            title = stringResource(R.string.dhcp_pool),
            subtitle = stringResource(R.string.dhcp_pool_summary),
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(poolStart, onPoolStartChange, label = { Text(stringResource(R.string.pool_start)) }, modifier = Modifier.weight(1f), singleLine = true)
                OutlinedTextField(poolLimit, onPoolLimitChange, label = { Text(stringResource(R.string.pool_size)) }, modifier = Modifier.weight(1f), singleLine = true)
            }
            OptionSelector(stringResource(R.string.lease_time), leaseTime, clientLeaseTimeOptions, onLeaseTimeChange)
            PrimaryActionButton(
                label = stringResource(R.string.save_dhcp),
                onClick = onSaveDhcp,
                enabled = poolStart.isNotBlank() && poolLimit.isNotBlank() && leaseTime.isNotBlank(),
            )
        }
    }
}

@Composable
private fun ClientBackRow(onBack: () -> Unit, label: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = onBack) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = label)
        }
        Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
    }
}

private fun clientGroupKey(client: NetworkClientDto): String = when {
    !client.online -> "offline"
    client.connectionType == "wifi" -> "wifi:${client.wifiSsid.orEmpty().ifBlank { "wifi" }}"
    client.connectionType == "wired" -> "wired"
    else -> "network"
}

@Composable
private fun clientGroupTitle(key: String, clients: List<NetworkClientDto>): String = when {
    key == "offline" -> stringResource(R.string.offline_clients)
    key == "wired" -> stringResource(R.string.wired_clients)
    key.startsWith("wifi:") -> clients.firstOrNull()?.wifiSsid?.takeIf(String::isNotBlank) ?: stringResource(R.string.wifi_clients)
    else -> stringResource(R.string.home_network)
}

@Composable
private fun clientGroupSubtitle(clients: List<NetworkClientDto>): String {
    val online = clients.count(NetworkClientDto::online)
    val bandResources = clients.filter(NetworkClientDto::online).mapNotNull { wifiBandResource(it.wifiBand) }.distinct()
    val bands = mutableListOf<String>()
    for (resource in bandResources) bands += stringResource(resource)
    val connection = bands.takeIf { it.isNotEmpty() }?.joinToString(" · ")
    return listOfNotNull(connection, stringResource(R.string.client_segment_summary, clients.size, online)).joinToString(" · ")
}

@Composable
private fun clientDisplayName(client: NetworkClientDto): String = clientDisplayNameRaw(client)
    .ifBlank { stringResource(R.string.client_unknown) }

private fun clientDisplayNameRaw(client: NetworkClientDto): String {
    val candidate = client.displayName?.trim()?.takeUnless { it.isBlank() }
        ?: client.hostname?.trim()?.takeUnless { it.isBlank() }
        ?: ""
    return candidate.takeUnless(::looksLikeAddress).orEmpty()
}

private fun looksLikeAddress(value: String): Boolean = value.contains(":") ||
    Regex("^\\d{1,3}(?:\\.\\d{1,3}){3}$").matches(value)

private fun compactMac(mac: String): String = mac.lowercase(Locale.ROOT)

@Composable
private fun clientConnectionLabel(client: NetworkClientDto): String = when (client.connectionType) {
    "wifi" -> formatWifiBand(client.wifiBand) ?: stringResource(R.string.wifi)
    "wired" -> stringResource(R.string.client_connection_wired)
    else -> stringResource(R.string.client_connection_unknown)
}

@Composable
private fun formatWifiBand(band: String?): String? {
    val resource = wifiBandResource(band) ?: return null
    return stringResource(resource)
}

private fun wifiBandResource(band: String?): Int? = when (band?.lowercase(Locale.ROOT)) {
    "2g", "2.4g", "2.4ghz" -> R.string.client_band_2g
    "5g", "5ghz" -> R.string.client_band_5g
    "6g", "6ghz" -> R.string.client_band_6g
    else -> null
}

private fun clientIcon(client: NetworkClientDto): ImageVector {
    val identity = listOfNotNull(client.displayName, client.hostname, client.vendor).joinToString(" ").lowercase(Locale.ROOT)
    return when {
        listOf("phone", "redmi", "poco", "xiaomi", "huawei", "mobile", "android", "iphone").any(identity::contains) -> Icons.Default.PhoneAndroid
        listOf("pc", "desktop", "computer", "laptop", "windows", "macbook").any(identity::contains) -> Icons.Default.Computer
        listOf("router", "openwrt", "gateway").any(identity::contains) -> Icons.Default.Router
        client.connectionType == "wifi" -> Icons.Default.Wifi
        else -> Icons.Default.DevicesOther
    }
}

private fun formatClientBytes(value: Long): String = when {
    value >= 1024L * 1024 * 1024 -> String.format(Locale.getDefault(), "%.1f GB", value / (1024.0 * 1024 * 1024))
    value >= 1024L * 1024 -> String.format(Locale.getDefault(), "%.1f MB", value / (1024.0 * 1024))
    value >= 1024L -> String.format(Locale.getDefault(), "%.1f KB", value / 1024.0)
    else -> "$value B"
}

private fun formatLinkRate(value: Long): String = when {
    value >= 1_000_000 -> String.format(Locale.getDefault(), "%.1f Gbit/s", value / 1_000_000.0)
    value >= 1_000 -> String.format(Locale.getDefault(), "%.0f Mbit/s", value / 1_000.0)
    else -> "$value Kbit/s"
}

private fun formatClientDate(value: String?): String = runCatching {
    Instant.parse(value).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
}.getOrNull().orEmpty()
