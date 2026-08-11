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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.wrtmonitor.app.api.dto.JsonArray
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.dto.ClientProfileDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.NetworkClientDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.data.RouterRepository
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

internal enum class ClientsView { List, Details, Settings }

internal enum class ClientsFilter { All, Online, Recent, Offline }

internal val clientWeekdayOptions = listOf("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    .map { SelectOption(it, it.uppercase()) }
internal val clientPriorityOptions = listOf("low", "normal", "high", "realtime")
    .map { SelectOption(it, it) }
internal val clientLeaseTimeOptions = listOf("30m", "1h", "6h", "12h", "24h", "72h", "168h")
    .map { SelectOption(it, it) }
internal val clientIpv6PrefixOptions = listOf("48", "52", "56", "60", "64")
    .map { SelectOption(it, "/$it") }

@Composable
fun ClientsControlScreen(
    serverUrl: String,
    accessToken: String,
    device: DeviceDto,
    onSessionExpired: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val repository = remember(serverUrl, accessToken) { RouterRepository(serverUrl, accessToken) }
    var telemetry by remember(device.id) { mutableStateOf<TelemetryDto?>(null) }
    var clients by remember(device.id) { mutableStateOf<List<NetworkClientDto>>(emptyList()) }
    var profiles by remember(device.id) { mutableStateOf<List<ClientProfileDto>>(emptyList()) }
    var view by rememberSaveable(device.id) { mutableStateOf(ClientsView.List) }
    var selectedClientId by rememberSaveable(device.id) { mutableStateOf<String?>(null) }
    var search by rememberSaveable(device.id) { mutableStateOf("") }
    var filter by rememberSaveable(device.id) { mutableStateOf(ClientsFilter.All) }
    var profileName by remember(device.id) { mutableStateOf("") }
    var profileBlocked by remember(device.id) { mutableStateOf(false) }
    var poolStart by remember(device.id) { mutableStateOf("") }
    var poolLimit by remember(device.id) { mutableStateOf("") }
    var leaseTime by remember(device.id) { mutableStateOf("") }
    var dhcpInitialized by remember(device.id) { mutableStateOf(false) }
    var ipv6Enabled by remember(device.id) { mutableStateOf(false) }
    var ipv6Prefix by remember(device.id) { mutableStateOf("64") }
    var ipv6Ra by remember(device.id) { mutableStateOf("disabled") }
    var ipv6Dhcp by remember(device.id) { mutableStateOf("disabled") }
    var ipv6Ndp by remember(device.id) { mutableStateOf("disabled") }
    var loading by remember(device.id) { mutableStateOf(false) }
    var message by remember(device.id) { mutableStateOf("") }
    var messageIsError by remember(device.id) { mutableStateOf(false) }
    var pendingCommand by remember(device.id) { mutableStateOf<PendingSafeCommand?>(null) }
    val commandQueued = stringResource(R.string.command_queued)
    val leaseQueued = stringResource(R.string.lease_queued)

    val refresh: () -> Unit = {
        scope.launch {
            loading = true
            when (val result = repository.latestTelemetry(device.id)) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    if (!dhcpInitialized) {
                        val pools = result.data.payload?.optJsonObject("dhcp")?.optJsonArray("pools")
                        val lanPool = pools?.let { array ->
                            (0 until array.length()).mapNotNull(array::optJsonObject)
                                .firstOrNull { it.optString("interface") == "lan" }
                        }
                        if (lanPool != null) {
                            poolStart = lanPool.optInt("start").takeIf { it > 0 }?.toString().orEmpty()
                            poolLimit = lanPool.optInt("limit").takeIf { it > 0 }?.toString().orEmpty()
                            leaseTime = lanPool.optString("leasetime")
                            ipv6Ra = lanPool.optString("ra", "disabled")
                            ipv6Dhcp = lanPool.optString("dhcpv6", "disabled")
                            ipv6Ndp = lanPool.optString("ndp", "disabled")
                        }
                        val interfaces = result.data.network?.optJsonArray("interfaces")
                        val lan = interfaces?.let { array ->
                            (0 until array.length()).mapNotNull(array::optJsonObject)
                                .firstOrNull { it.optString("interface") == "lan" }
                        }
                        val configuredPrefix = lan?.optString("ip6assign").orEmpty()
                        ipv6Enabled = configuredPrefix.isNotBlank()
                        if (configuredPrefix.isNotBlank()) ipv6Prefix = configuredPrefix
                        dhcpInitialized = true
                    }
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            when (val result = repository.clients(device.id)) {
                is ApiResult.Success -> clients = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            when (val result = repository.clientProfiles(device.id)) {
                is ApiResult.Success -> profiles = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            loading = false
        }
    }

    fun queue(type: String, payload: JsonObject) {
        scope.launch {
            when (val result = repository.createCommand(device.id, type, payload, true)) {
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

    fun saveClient(
        client: NetworkClientDto,
        name: String,
        deviceType: String,
        profileId: String?,
        policy: JsonObject,
    ) {
        scope.launch {
            val storedPolicy = if (profileId == null) policy else JsonObject()
            when (val update = repository.updateClient(
                device.id,
                client.id,
                name,
                deviceType,
                profileId,
                storedPolicy,
            )) {
                is ApiResult.Success -> when (val apply = repository.applyClientPolicy(device.id, client.id)) {
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
            onSave = { name, deviceType, profileId, policy ->
                saveClient(selectedClient, name, deviceType, profileId, policy)
            },
            onSetLease = { hostname, ip ->
                pendingCommand = PendingSafeCommand(
                    "dhcp.set_lease",
                    JsonObject().put("hostname", hostname).put("mac", selectedClient.mac).put("ip", ip),
                    leaseQueued,
                )
            },
            onDeleteLease = {
                pendingCommand = PendingSafeCommand(
                    "dhcp.delete_lease",
                    JsonObject().put("mac", selectedClient.mac),
                    commandQueued,
                )
            },
        )
        view == ClientsView.Settings -> ClientsSettings(
            profiles = profiles,
            canManageProfiles = capabilities["clients.policy"] == true,
            canConfigureDhcp = capabilities["dhcp.configure"] == true,
            canConfigureIpv6 = capabilities["network.ipv6.configure"] == true,
            topology = telemetry?.network?.optJsonObject("topology"),
            canConfigureSegments = capabilities["network.segments.configure"] == true,
            canConfigureVlans = capabilities["network.vlan.configure"] == true,
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
            ipv6Enabled = ipv6Enabled,
            onIpv6EnabledChange = { ipv6Enabled = it },
            ipv6Prefix = ipv6Prefix,
            onIpv6PrefixChange = { ipv6Prefix = it },
            ipv6Ra = ipv6Ra,
            onIpv6RaChange = { ipv6Ra = it },
            ipv6Dhcp = ipv6Dhcp,
            onIpv6DhcpChange = { ipv6Dhcp = it },
            ipv6Ndp = ipv6Ndp,
            onIpv6NdpChange = { ipv6Ndp = it },
            onBack = { view = ClientsView.List },
            onCreateProfile = {
                scope.launch {
                    when (val result = repository.createClientProfile(device.id, profileName, profileBlocked)) {
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
                    when (val result = repository.deleteClientProfile(device.id, profileId)) {
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
                    JsonObject().put("interface", "lan").put("start", poolStart)
                        .put("limit", poolLimit).put("leasetime", leaseTime),
                    commandQueued,
                )
            },
            onSaveIpv6 = {
                pendingCommand = PendingSafeCommand(
                    "network.set_ipv6",
                    JsonObject().put("interface", "lan").put("enabled", ipv6Enabled)
                        .put("assignment_length", ipv6Prefix.toIntOrNull() ?: 64)
                        .put("ra", ipv6Ra).put("dhcpv6", ipv6Dhcp).put("ndp", ipv6Ndp),
                    commandQueued,
                )
            },
            onPrepareCommand = { pendingCommand = it },
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
            repository = repository,
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
