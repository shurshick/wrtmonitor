package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.wrtmonitor.app.api.dto.JsonArray
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.dto.ManagementOptionsDto
import ru.wrtmonitor.app.api.dto.CommandDto
import ru.wrtmonitor.app.api.dto.CommandPreviewDto
import ru.wrtmonitor.app.api.dto.ClientProfileDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.NetworkClientDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.data.RouterRepository
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
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
@Composable
fun NetworkControlScreen(
    serverUrl: String,
    accessToken: String,
    device: DeviceDto,
    onSessionExpired: () -> Unit,
    mode: NetworkScreenMode = NetworkScreenMode.Internet,
) {
    val scope = rememberCoroutineScope()
    val repository = remember(serverUrl, accessToken) { RouterRepository(serverUrl, accessToken) }
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var managementOptions by remember { mutableStateOf<ManagementOptionsDto?>(null) }
    var loading by remember(device.id) { mutableStateOf(true) }
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
    var dotProvider by remember { mutableStateOf("cloudflare") }
    var dotEnabled by remember { mutableStateOf(false) }
    var dohProvider by remember { mutableStateOf("cloudflare") }
    var dohEnabled by remember { mutableStateOf(false) }
    var forwardName by remember { mutableStateOf("") }
    var forwardExternalPort by remember { mutableStateOf("") }
    var forwardInternalIp by remember { mutableStateOf("") }
    var forwardInternalPort by remember { mutableStateOf("") }
    var redirectSection by remember { mutableStateOf("") }
    var sqmEnabled by remember { mutableStateOf(true) }
    var sqmInterface by remember { mutableStateOf("") }
    var sqmDownload by remember { mutableStateOf("") }
    var sqmUpload by remember { mutableStateOf("") }
    var sqmProfile by remember { mutableStateOf("balanced") }
    var sqmQdisc by remember { mutableStateOf("cake") }
    var sqmScript by remember { mutableStateOf("piece_of_cake.qos") }
    var sqmOptions by remember { mutableStateOf("") }
    var multiWanEnabled by remember { mutableStateOf(true) }
    var primaryWan by remember { mutableStateOf("") }
    var secondaryWan by remember { mutableStateOf("") }
    var multiWanTrackIps by remember { mutableStateOf("1.1.1.1, 8.8.8.8") }
    var multiWanCheckInterval by remember { mutableStateOf("5") }
    var multiWanDownChecks by remember { mutableStateOf("3") }
    var multiWanUpChecks by remember { mutableStateOf("3") }
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
    var zoneSection by remember { mutableStateOf("") }
    var zoneInput by remember { mutableStateOf("REJECT") }
    var zoneOutput by remember { mutableStateOf("ACCEPT") }
    var zoneForward by remember { mutableStateOf("REJECT") }
    var zoneMasquerade by remember { mutableStateOf(false) }
    var forwardingSection by remember { mutableStateOf("") }
    var forwardingSource by remember { mutableStateOf("") }
    var forwardingDestination by remember { mutableStateOf("") }
    var ruleNameValue by remember { mutableStateOf("") }
    var ruleSection by remember { mutableStateOf("") }
    var ruleSource by remember { mutableStateOf("") }
    var ruleDestination by remember { mutableStateOf("") }
    var ruleProtocol by remember { mutableStateOf("tcpudp") }
    var ruleTarget by remember { mutableStateOf("ACCEPT") }
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
        loading = true
        scope.launch {
            when (val result = repository.latestTelemetry(device.id)) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    if (!formInitialized) {
                        val items = result.data.network?.optJsonArray("interfaces")
                        fun findInterface(name: String): JsonObject? = items?.let { array ->
                            (0 until array.length()).mapNotNull(array::optJsonObject)
                                .firstOrNull { it.optString("interface") == name }
                        }
                        val lan = findInterface("lan")
                        val wan = findInterface("wan")
                        lanIp = lan?.optJsonArray("ipv4")?.optString(0).orEmpty()
                        lanNetmask = lan?.optString("netmask").orEmpty()
                        wanProtocol = wan?.optString("proto").orEmpty()
                        wanIp = wan?.optJsonArray("ipv4")?.optString(0).orEmpty()
                        wanNetmask = wan?.optString("netmask").orEmpty()
                        wanGateway = wan?.optString("gateway").orEmpty()
                        wanDns = wan?.optJsonArray("dns")?.let { array ->
                            (0 until array.length()).joinToString(", ") { array.optString(it) }
                        }.orEmpty()
                        dnsServers = wanDns
                        val privacy = result.data.network?.optJsonObject("dns_privacy")
                        val dot = privacy?.optJsonObject("dot")
                        val doh = privacy?.optJsonObject("doh")
                        dotEnabled = dot?.optBoolean("running", false) == true
                        dohEnabled = doh?.optBoolean("running", false) == true
                        dotProvider = encryptedDnsProviderFromValue(dot?.optString("provider").orEmpty())
                        dohProvider = encryptedDnsProviderFromValue(doh?.optString("resolver_url").orEmpty())
                        interfaceName = wan?.optString("interface").orEmpty()
                        sqmInterface = wan?.optString("device").orEmpty()
                        primaryWan = wan?.optString("interface").orEmpty()
                        val mwan = result.data.network?.optJsonObject("mwan3")
                        multiWanEnabled = mwan?.optBoolean("enabled", false) == true
                        val members = mwan?.optJsonArray("members")
                        for (index in 0 until (members?.length() ?: 0)) {
                            val member = members?.optJsonObject(index) ?: continue
                            when (member.optString("role")) {
                                "primary" -> {
                                    primaryWan = member.optString("interface", primaryWan)
                                    multiWanTrackIps = member.optJsonArray("track_ips")?.let { values ->
                                        (0 until values.length()).joinToString(", ") { values.optString(it) }
                                    }.orEmpty().ifBlank { multiWanTrackIps }
                                    multiWanCheckInterval = member.optInt("interval", 5).toString()
                                    multiWanDownChecks = member.optInt("down", 3).toString()
                                    multiWanUpChecks = member.optInt("up", 3).toString()
                                }
                                "secondary" -> secondaryWan = member.optString("interface")
                            }
                        }
                        formInitialized = true
                    }
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            when (val result = repository.managementOptions(device.id)) {
                is ApiResult.Success -> managementOptions = result.data
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            loading = false
        }
        Unit
    }
    LaunchedEffect(device.id) { refresh() }
    val interfaces = telemetry?.network?.optJsonArray("interfaces")
        ?: telemetry?.payload?.optJsonObject("network")?.optJsonArray("interfaces")
        ?: telemetry?.payload?.optJsonObject("network")?.optJsonArray("interface")
    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()
    val networkDevices = telemetry?.payload?.optJsonObject("network_devices")
    val networkDeviceNames = remember(networkDevices?.toString()) {
        buildList {
            val keys = networkDevices?.keys()
            while (keys?.hasNext() == true) add(keys.next())
        }.sorted()
    }
    val telemetryInterfaceOptions = interfaces?.let { array ->
        (0 until array.length()).mapNotNull(array::optJsonObject)
            .flatMap { listOf(it.optString("interface"), it.optString("device")) }
            .filter(String::isNotBlank).distinct().map { SelectOption(it, it) }
    }.orEmpty()
    val interfaceOptions = managementOptions?.interfaces.orEmpty().map { SelectOption(it, it) }
        .ifEmpty { telemetryInterfaceOptions }
    val routerNetmaskOptions = managementOptions?.netmasks.orEmpty().map {
        SelectOption(it.value, "/${it.metadata} · ${it.value}")
    }.ifEmpty { listOf(SelectOption(wanNetmask, wanNetmask)) }
    val telemetryFirewallZoneOptions = telemetry?.network?.optJsonArray("firewall_zones")?.let { array ->
        (0 until array.length()).mapNotNull(array::optJsonObject)
            .map { it.optString("name") }
            .filter(String::isNotBlank)
            .distinct()
            .map { SelectOption(it, it) }
    }.orEmpty()
    val firewallZoneOptions = listOf(SelectOption("*", stringResource(R.string.any_zone))) +
        managementOptions?.firewallZones.orEmpty().map { SelectOption(it, it) }
            .ifEmpty { telemetryFirewallZoneOptions }
    val firewallZones = telemetry?.network?.optJsonArray("firewall_zones") ?: JsonArray()
    val firewallForwardings = telemetry?.network?.optJsonArray("firewall_forwardings") ?: JsonArray()
    val firewallRules = telemetry?.network?.optJsonArray("firewall_rules") ?: JsonArray()
    val firewallRedirects = telemetry?.network?.optJsonArray("firewall_redirects") ?: JsonArray()
    val vpn = telemetry?.payload?.optJsonObject("vpn")
    val interfacesRequestQueued = stringResource(R.string.interfaces_request_queued)
    val genericCommandQueued = stringResource(R.string.command_queued)
    fun queue(type: String, payload: JsonObject, success: String) {
        scope.launch {
            when (val result = repository.createCommand(device.id, type, payload, true)) {
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
    if (loading && telemetry == null) {
        SectionCard(stringResource(R.string.loading_data)) { CircularProgressIndicator(Modifier.size(24.dp)) }
    } else if (telemetry?.isStale == true || telemetry?.dataState?.kind in setOf("stale", "error", "unsupported")) {
        MessageBanner(
            when (telemetry?.dataState?.kind) {
                "unsupported" -> stringResource(R.string.unsupported_data)
                "error" -> telemetry?.dataState?.reason ?: stringResource(R.string.data_error)
                else -> stringResource(R.string.stale_telemetry)
            },
            error = telemetry?.dataState?.kind == "error",
        )
    }
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
        val wireguardCount = vpn?.optJsonObject("wireguard")?.optJsonArray("interfaces")?.length() ?: 0
        val openVpnService = vpn?.optJsonObject("openvpn")?.optString("service") ?: stringResource(R.string.no_data)
        val policyService = vpn?.optJsonObject("policy")?.optString("service") ?: stringResource(R.string.no_data)
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
                val item = interfaces.optJsonObject(index)
                val title = item?.optString("interface", item.optString("name", "interface")) ?: "interface"
                val isUp = item?.optBoolean("up", false) == true
                val details = listOfNotNull(
                    item?.optString("proto").takeUnless { it.isNullOrBlank() },
                    item?.optString("device").takeUnless { it.isNullOrBlank() },
                    item?.optJsonArray("ipv4")?.optString(0).takeUnless { it.isNullOrBlank() },
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
                        when (val result = repository.createCommand(
                            device.id,
                            "network.interfaces",
                            JsonObject(),
                            confirmed = true,
                        )) {
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
    if (mode == NetworkScreenMode.Internet && networkDeviceNames.isNotEmpty()) {
        ExpandableSettingsCard(
            stringResource(R.string.physical_network_devices),
            stringResource(R.string.interfaces_count, networkDeviceNames.size),
        ) {
            networkDeviceNames.forEachIndexed { index, name ->
                val item = networkDevices?.optJsonObject(name)
                val carrier = item?.optBoolean("carrier", false) == true
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(name, style = MaterialTheme.typography.titleSmall)
                        Text(
                            listOfNotNull(
                                item?.optInt("speed_mbps")?.takeIf { it > 0 }?.let { "$it Mbit/s" },
                                item?.optString("duplex")?.takeIf(String::isNotBlank),
                                item?.optInt("mtu")?.takeIf { it > 0 }?.let { "MTU $it" },
                            ).joinToString(" · ").ifBlank { stringResource(R.string.no_data) },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            "↓ ${formatClientBytes(item?.optLong("rx_bytes") ?: 0)} · ↑ ${formatClientBytes(item?.optLong("tx_bytes") ?: 0)}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    StatusPill(if (carrier) stringResource(R.string.link_up) else stringResource(R.string.link_down), carrier)
                }
                if (index < networkDeviceNames.lastIndex) HorizontalDivider()
            }
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["network.wan.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.wan_settings), wanProtocol.uppercase()) {
            OptionSelector(stringResource(R.string.connection_type), wanProtocol, wanProtocolOptions, { wanProtocol = it })
            if (wanProtocol == "static") {
                OutlinedTextField(wanIp, { wanIp = it }, label = { Text(stringResource(R.string.ip_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OptionSelector(stringResource(R.string.netmask), wanNetmask, routerNetmaskOptions, { wanNetmask = it })
                OutlinedTextField(wanGateway, { wanGateway = it }, label = { Text(stringResource(R.string.gateway)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            }
            if (wanProtocol == "pppoe") {
                OutlinedTextField(wanUsername, { wanUsername = it }, label = { Text(stringResource(R.string.username)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(wanPassword, { wanPassword = it }, label = { Text(stringResource(R.string.password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
            }
            OutlinedTextField(wanDns, { wanDns = it }, label = { Text(stringResource(R.string.dns_servers)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(
                label = stringResource(R.string.save_wan),
                onClick = { pendingCommand = PendingSafeCommand("network.set_wan", JsonObject().put("interface", "wan").put("protocol", wanProtocol).put("ip_address", wanIp).put("netmask", wanNetmask).put("gateway", wanGateway).put("dns", wanDns).put("username", wanUsername).put("password", wanPassword), genericCommandQueued) },
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["network.lan.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.lan_settings), "$lanIp · $lanNetmask") {
            OutlinedTextField(lanIp, { lanIp = it }, label = { Text(stringResource(R.string.router_ip)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OptionSelector(stringResource(R.string.netmask), lanNetmask, routerNetmaskOptions, { lanNetmask = it })
            PrimaryActionButton(
                label = stringResource(R.string.save_lan),
                onClick = { pendingCommand = PendingSafeCommand("network.set_lan", JsonObject().put("interface", "lan").put("ip_address", lanIp).put("netmask", lanNetmask), genericCommandQueued) },
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["dns.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.dns_servers), dnsServers) {
            OutlinedTextField(dnsServers, { dnsServers = it }, label = { Text(stringResource(R.string.dns_servers)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(
                label = stringResource(R.string.apply_dns),
                onClick = { pendingCommand = PendingSafeCommand("dns.set_servers", JsonObject().put("servers", dnsServers), genericCommandQueued) },
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities.keys.any { it.startsWith("dns.") }) {
        ExpandableSettingsCard(stringResource(R.string.encrypted_dns), stringResource(R.string.encrypted_dns_summary)) {
            Text("DNS over TLS", style = MaterialTheme.typography.titleSmall)
            if (capabilities["dns.dot.configure"] == true) {
                OptionSelector(stringResource(R.string.dns_provider), dotProvider, encryptedDnsProviderOptions, { dotProvider = it })
                SwitchSettingRow(stringResource(R.string.enabled), checked = dotEnabled, onCheckedChange = { dotEnabled = it })
                PrimaryActionButton(
                    stringResource(R.string.apply_dot),
                    { pendingCommand = PendingSafeCommand("dns.set_dot", JsonObject().put("provider", dotProvider).put("enabled", dotEnabled), genericCommandQueued) },
                    Modifier.align(Alignment.End),
                )
            } else if (capabilities["dns.encrypted.install"] == true) {
                SecondaryActionButton(
                    stringResource(R.string.install_dot),
                    { pendingCommand = PendingSafeCommand("dns.install_dot", JsonObject(), genericCommandQueued) },
                    Modifier.align(Alignment.End),
                )
            }
            HorizontalDivider()
            Text("DNS over HTTPS", style = MaterialTheme.typography.titleSmall)
            if (capabilities["dns.doh.configure"] == true) {
                OptionSelector(stringResource(R.string.dns_provider), dohProvider, encryptedDnsProviderOptions, { dohProvider = it })
                SwitchSettingRow(stringResource(R.string.enabled), checked = dohEnabled, onCheckedChange = { dohEnabled = it })
                PrimaryActionButton(
                    stringResource(R.string.apply_doh),
                    { pendingCommand = PendingSafeCommand("dns.set_doh", JsonObject().put("provider", dohProvider).put("enabled", dohEnabled), genericCommandQueued) },
                    Modifier.align(Alignment.End),
                )
            } else if (capabilities["dns.encrypted.install"] == true) {
                SecondaryActionButton(
                    stringResource(R.string.install_doh),
                    { pendingCommand = PendingSafeCommand("dns.install_doh", JsonObject(), genericCommandQueued) },
                    Modifier.align(Alignment.End),
                )
            }
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["qos.sqm"] == true) {
        ExpandableSettingsCard(stringResource(R.string.sqm_title), stringResource(R.string.sqm_summary)) {
            SwitchSettingRow(stringResource(R.string.sqm_enabled), checked = sqmEnabled, onCheckedChange = { sqmEnabled = it })
            val sqmProfiles = managementOptions?.sqmProfiles.orEmpty().map { SelectOption(it.value, it.label) }
            OptionSelector(stringResource(R.string.sqm_profile), sqmProfile, sqmProfiles, { selected ->
                sqmProfile = selected
                managementOptions?.sqmProfiles?.firstOrNull { it.value == selected }?.metadata?.split('|')?.let { metadata ->
                    sqmQdisc = metadata.getOrNull(0).orEmpty().ifBlank { "cake" }
                    sqmScript = metadata.getOrNull(1).orEmpty().ifBlank { "piece_of_cake.qos" }
                    sqmOptions = metadata.getOrNull(2).orEmpty()
                }
            })
            OptionSelector(stringResource(R.string.sqm_interface), sqmInterface, interfaceOptions, { sqmInterface = it })
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(sqmDownload, { sqmDownload = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.download_limit)) }, modifier = Modifier.weight(1f), singleLine = true)
                OutlinedTextField(sqmUpload, { sqmUpload = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.upload_limit)) }, modifier = Modifier.weight(1f), singleLine = true)
            }
            PrimaryActionButton(
                label = stringResource(R.string.apply_sqm),
                onClick = { pendingCommand = PendingSafeCommand("qos.set_sqm", JsonObject().put("enabled", sqmEnabled).put("interface", sqmInterface).put("download_kbps", sqmDownload).put("upload_kbps", sqmUpload).put("profile", sqmProfile).put("qdisc", sqmQdisc).put("script", sqmScript).put("qdisc_options", sqmOptions).put("schedule", JsonObject().put("enabled", false).put("weekdays", JsonArray()).put("start", "").put("stop", "")), genericCommandQueued) },
                enabled = sqmInterface.isNotBlank() && sqmDownload.isNotBlank() && sqmUpload.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["firewall.port_forward"] == true) {
        ExpandableSettingsCard(stringResource(R.string.port_forwarding), stringResource(R.string.items_count, firewallRedirects.length())) {
            for (index in 0 until firewallRedirects.length()) {
                val item = firewallRedirects.optJsonObject(index) ?: continue
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(item.optString("name"), style = MaterialTheme.typography.titleSmall)
                        Text(
                            "${item.optString("src", "wan")}:${item.optString("src_port", "*")} → ${item.optString("dest_ip")}:${item.optString("dest_port", "*")}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    TextButton(onClick = {
                        redirectSection = item.optString("section")
                        forwardName = item.optString("name")
                        forwardExternalPort = item.optString("src_port")
                        forwardInternalIp = item.optString("dest_ip")
                        forwardInternalPort = item.optString("dest_port")
                    }) { Text(stringResource(R.string.edit)) }
                    TextButton(onClick = {
                        pendingCommand = PendingSafeCommand(
                            "firewall.delete_redirect",
                            JsonObject().put("section", item.optString("section")).put("name", item.optString("name")),
                            genericCommandQueued,
                        )
                    }) { Text(stringResource(R.string.delete)) }
                }
                if (index < firewallRedirects.length() - 1) HorizontalDivider()
            }
            OutlinedTextField(forwardName, { forwardName = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(forwardExternalPort, { forwardExternalPort = it }, label = { Text(stringResource(R.string.external_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(forwardInternalIp, { forwardInternalIp = it }, label = { Text(stringResource(R.string.internal_ip)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(forwardInternalPort, { forwardInternalPort = it }, label = { Text(stringResource(R.string.internal_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow {
                PrimaryActionButton(
                    label = stringResource(R.string.add_port_forward),
                    onClick = { pendingCommand = PendingSafeCommand("firewall.set_redirect", JsonObject().put("section", redirectSection).put("name", forwardName).put("enabled", true).put("src", "wan").put("dest", "lan").put("protocol", "tcp").put("src_port", forwardExternalPort).put("dest_ip", forwardInternalIp).put("dest_port", forwardInternalPort).put("target", "DNAT"), genericCommandQueued) },
                    enabled = forwardName.isNotBlank() && forwardExternalPort.isNotBlank() && forwardInternalIp.isNotBlank() && forwardInternalPort.isNotBlank(),
                )
                TextButton(onClick = { pendingCommand = PendingSafeCommand("firewall.delete_redirect", JsonObject().put("section", redirectSection).put("name", forwardName), genericCommandQueued) }, enabled = forwardName.isNotBlank()) {
                    Text(stringResource(R.string.delete_port_forward))
                }
            }
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["network.multiwan.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.multiwan_settings), "$primaryWan → $secondaryWan") {
            SwitchSettingRow(stringResource(R.string.multiwan_settings), checked = multiWanEnabled, onCheckedChange = { multiWanEnabled = it })
            OptionSelector(stringResource(R.string.primary_wan), primaryWan, interfaceOptions, { primaryWan = it })
            OptionSelector(stringResource(R.string.secondary_wan), secondaryWan, interfaceOptions, { secondaryWan = it })
            OutlinedTextField(multiWanTrackIps, { multiWanTrackIps = it }, label = { Text(stringResource(R.string.multiwan_track_ips)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(multiWanCheckInterval, { multiWanCheckInterval = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.multiwan_interval)) }, modifier = Modifier.weight(1f), singleLine = true)
                OutlinedTextField(multiWanDownChecks, { multiWanDownChecks = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.multiwan_down_checks)) }, modifier = Modifier.weight(1f), singleLine = true)
                OutlinedTextField(multiWanUpChecks, { multiWanUpChecks = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.multiwan_up_checks)) }, modifier = Modifier.weight(1f), singleLine = true)
            }
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("network.set_multiwan", JsonObject().put("enabled", multiWanEnabled).put("primary_interface", primaryWan).put("secondary_interface", secondaryWan).put("primary_metric", 10).put("secondary_metric", 20).put("track_ips", multiWanTrackIps).put("check_interval", multiWanCheckInterval.toIntOrNull() ?: 5).put("failure_interval", multiWanDownChecks.toIntOrNull() ?: 3).put("recovery_interval", multiWanUpChecks.toIntOrNull() ?: 3), genericCommandQueued) }, Modifier.align(Alignment.End), enabled = primaryWan.isNotBlank() && secondaryWan.isNotBlank())
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["network.routes.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.static_routes), routeTarget) {
            OutlinedTextField(routeName, { routeName = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(routeTarget, { routeTarget = it }, label = { Text(stringResource(R.string.route_target)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(routeGateway, { routeGateway = it }, label = { Text(stringResource(R.string.gateway)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(routeMetric, { routeMetric = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.route_metric)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow { PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("network.set_route", JsonObject().put("name", routeName).put("interface", "wan").put("target", routeTarget).put("gateway", routeGateway).put("metric", routeMetric.toIntOrNull() ?: 0), genericCommandQueued) }, enabled = routeName.isNotBlank() && routeTarget.isNotBlank()); TextButton({ pendingCommand = PendingSafeCommand("network.delete_route", JsonObject().put("name", routeName), genericCommandQueued) }, enabled = routeName.isNotBlank()) { Text(stringResource(R.string.delete)) } }
        }
    }
    if (mode == NetworkScreenMode.Internet && capabilities["network.ddns.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.ddns_settings), ddnsDomain) {
            OutlinedTextField(ddnsName, { ddnsName = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ddnsProvider, { ddnsProvider = it }, label = { Text(stringResource(R.string.provider)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ddnsDomain, { ddnsDomain = it }, label = { Text(stringResource(R.string.domain)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ddnsUser, { ddnsUser = it }, label = { Text(stringResource(R.string.username)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ddnsPassword, { ddnsPassword = it }, label = { Text(stringResource(R.string.password)) }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("network.set_ddns", JsonObject().put("name", ddnsName).put("enabled", true).put("provider", ddnsProvider).put("domain", ddnsDomain).put("username", ddnsUser).put("password", ddnsPassword).put("interface", "wan"), genericCommandQueued) }, Modifier.align(Alignment.End), enabled = ddnsDomain.isNotBlank())
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["firewall.upnp.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.upnp_settings), if (upnpEnabled) stringResource(R.string.enabled_value) else stringResource(R.string.disabled_value)) {
            SwitchSettingRow(stringResource(R.string.upnp_settings), checked = upnpEnabled, onCheckedChange = { upnpEnabled = it })
            SwitchSettingRow(stringResource(R.string.secure_mode), checked = upnpSecure, onCheckedChange = { upnpSecure = it })
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("network.set_upnp", JsonObject().put("enabled", upnpEnabled).put("secure_mode", upnpSecure), genericCommandQueued) }, Modifier.align(Alignment.End))
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["firewall.zones.configure"] == true) {
        SectionCard(
            title = stringResource(R.string.firewall_zones_list),
            subtitle = stringResource(R.string.items_count, firewallZones.length()),
        ) {
            for (index in 0 until firewallZones.length()) {
                val item = firewallZones.optJsonObject(index) ?: continue
                val itemName = item.optString("name")
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(itemName, style = MaterialTheme.typography.titleSmall)
                        Text(
                            listOf(item.optString("input"), item.optString("output"), item.optString("forward"))
                                .filter(String::isNotBlank).joinToString(" · "),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    TextButton(onClick = {
                        zoneSection = item.optString("section")
                        zoneNameValue = itemName
                        zoneNetworks = item.optJsonArray("networks")?.let { values ->
                            (0 until values.length()).joinToString(" ") { values.optString(it) }
                        } ?: item.optString("networks")
                        zoneInput = item.optString("input", "REJECT")
                        zoneOutput = item.optString("output", "ACCEPT")
                        zoneForward = item.optString("forward", "REJECT")
                        zoneMasquerade = item.optBoolean("masquerade")
                    }) { Text(stringResource(R.string.edit)) }
                    if (itemName !in setOf("lan", "wan")) {
                        TextButton(
                            onClick = {
                                pendingCommand = PendingSafeCommand(
                                    "firewall.delete_zone",
                                    JsonObject().put("section", item.optString("section")).put("name", itemName),
                                    genericCommandQueued,
                                )
                            },
                            enabled = item.optString("section").isNotBlank(),
                        ) { Text(stringResource(R.string.delete)) }
                    }
                }
                if (index < firewallZones.length() - 1) HorizontalDivider()
            }
        }
        ExpandableSettingsCard(stringResource(R.string.firewall_zone), zoneNameValue) {
            OutlinedTextField(zoneNameValue, { zoneNameValue = it }, label = { Text(stringResource(R.string.firewall_zone)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(zoneNetworks, { zoneNetworks = it }, label = { Text(stringResource(R.string.zone_networks)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OptionSelector(stringResource(R.string.firewall_input), zoneInput, firewallPolicyOptions, { zoneInput = it })
            OptionSelector(stringResource(R.string.firewall_output), zoneOutput, firewallPolicyOptions, { zoneOutput = it })
            OptionSelector(stringResource(R.string.firewall_forward), zoneForward, firewallPolicyOptions, { zoneForward = it })
            SwitchSettingRow(stringResource(R.string.masquerading), checked = zoneMasquerade, onCheckedChange = { zoneMasquerade = it })
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("firewall.set_zone", JsonObject().put("section", zoneSection).put("name", zoneNameValue).put("networks", JsonArray(zoneNetworks.split(' ').filter(String::isNotBlank))).put("input", zoneInput).put("output", zoneOutput).put("forward", zoneForward).put("masquerade", zoneMasquerade), genericCommandQueued) }, Modifier.align(Alignment.End), enabled = zoneNameValue.isNotBlank() && zoneNetworks.isNotBlank())
        }
        SectionCard(
            title = stringResource(R.string.firewall_forwardings),
            subtitle = stringResource(R.string.items_count, firewallForwardings.length()),
        ) {
            for (index in 0 until firewallForwardings.length()) {
                val item = firewallForwardings.optJsonObject(index) ?: continue
                val src = item.optString("src")
                val dest = item.optString("dest")
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text("$src → $dest", modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                    TextButton(onClick = {
                        forwardingSection = item.optString("section")
                        forwardingSource = src
                        forwardingDestination = dest
                    }) { Text(stringResource(R.string.edit)) }
                    TextButton(
                        onClick = {
                            pendingCommand = PendingSafeCommand(
                                "firewall.delete_forwarding",
                                JsonObject().put("section", item.optString("section")).put("src", src).put("dest", dest),
                                genericCommandQueued,
                            )
                        },
                        enabled = item.optString("section").isNotBlank(),
                    ) { Text(stringResource(R.string.delete)) }
                }
                if (index < firewallForwardings.length() - 1) HorizontalDivider()
            }
            OptionSelector(stringResource(R.string.source_zone), forwardingSource, firewallZoneOptions, { forwardingSource = it })
            OptionSelector(stringResource(R.string.destination_zone), forwardingDestination, firewallZoneOptions, { forwardingDestination = it })
            PrimaryActionButton(
                stringResource(R.string.save),
                { pendingCommand = PendingSafeCommand("firewall.set_forwarding", JsonObject().put("section", forwardingSection).put("src", forwardingSource).put("dest", forwardingDestination).put("enabled", true), genericCommandQueued) },
                Modifier.align(Alignment.End),
                enabled = forwardingSource.isNotBlank() && forwardingDestination.isNotBlank(),
            )
        }
    }
    if (mode == NetworkScreenMode.Rules && capabilities["firewall.rules.configure"] == true) {
        SectionCard(
            title = stringResource(R.string.firewall_rules_list),
            subtitle = stringResource(R.string.items_count, firewallRules.length()),
        ) {
            for (index in 0 until firewallRules.length()) {
                val item = firewallRules.optJsonObject(index) ?: continue
                val itemName = item.optString("name")
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(itemName, style = MaterialTheme.typography.titleSmall)
                        Text(
                            listOf(item.optString("src"), item.optString("dest"), item.optString("protocol"), item.optString("dest_port"), item.optString("target"))
                                .filter(String::isNotBlank).joinToString(" · "),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    TextButton(onClick = {
                        ruleSection = item.optString("section")
                        ruleNameValue = itemName
                        ruleSource = item.optString("src").ifBlank { "*" }
                        ruleDestination = item.optString("dest").ifBlank { "*" }
                        ruleProtocol = item.optString("protocol", "tcpudp").let { if (it == "tcp udp") "tcpudp" else it }
                        rulePort = item.optString("dest_port")
                        ruleTarget = item.optString("target", "ACCEPT")
                    }) { Text(stringResource(R.string.edit)) }
                    TextButton(
                        onClick = {
                            pendingCommand = PendingSafeCommand(
                                "firewall.delete_rule",
                                JsonObject().put("section", item.optString("section")).put("name", itemName),
                                genericCommandQueued,
                            )
                        },
                        enabled = item.optString("section").isNotBlank(),
                    ) { Text(stringResource(R.string.delete)) }
                }
                if (index < firewallRules.length() - 1) HorizontalDivider()
            }
        }
        ExpandableSettingsCard(stringResource(R.string.firewall_rule), ruleNameValue) {
            OutlinedTextField(ruleNameValue, { ruleNameValue = it }, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OptionSelector(stringResource(R.string.source_zone), ruleSource, firewallZoneOptions, { ruleSource = it })
            OptionSelector(stringResource(R.string.destination_zone), ruleDestination, firewallZoneOptions, { ruleDestination = it })
            OptionSelector(stringResource(R.string.protocol), ruleProtocol, firewallProtocolOptions, { ruleProtocol = it })
            OutlinedTextField(rulePort, { rulePort = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.internal_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OptionSelector(stringResource(R.string.action), ruleTarget, firewallPolicyOptions, { ruleTarget = it })
            ActionRow { PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("firewall.set_rule", JsonObject().put("section", ruleSection).put("name", ruleNameValue).put("src", ruleSource).put("dest", ruleDestination).put("protocol", ruleProtocol).put("dest_port", rulePort).put("target", ruleTarget), genericCommandQueued) }, enabled = ruleNameValue.isNotBlank() && ruleSource.isNotBlank()) }
        }
    }
    if (mode == NetworkScreenMode.Vpn && capabilities["vpn.wireguard.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.wireguard_interface), wgName) {
            OutlinedTextField(wgName, { wgName = it }, label = { Text(stringResource(R.string.interface_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgAddress, { wgAddress = it }, label = { Text(stringResource(R.string.tunnel_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPort, { wgPort = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.listen_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPrivateKey, { wgPrivateKey = it }, label = { Text(stringResource(R.string.private_key_optional)) }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow {
                PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("vpn.wireguard.set_interface", JsonObject().put("name", wgName).put("enabled", true).put("mode", "server").put("addresses", JsonArray(listOf(wgAddress))).put("listen_port", wgPort.toIntOrNull() ?: 51820).put("private_key", wgPrivateKey).put("mtu", 1420), genericCommandQueued) }, enabled = wgName.isNotBlank() && wgAddress.isNotBlank())
                TextButton({ pendingCommand = PendingSafeCommand("vpn.wireguard.delete_interface", JsonObject().put("name", wgName), genericCommandQueued) }, enabled = wgName.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
        ExpandableSettingsCard(stringResource(R.string.wireguard_peer), wgPeerName) {
            OutlinedTextField(wgName, { wgName = it }, label = { Text(stringResource(R.string.interface_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerName, { wgPeerName = it }, label = { Text(stringResource(R.string.peer_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerPublicKey, { wgPeerPublicKey = it }, label = { Text(stringResource(R.string.public_key)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerPresharedKey, { wgPeerPresharedKey = it }, label = { Text(stringResource(R.string.preshared_key_optional)) }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerAllowedIps, { wgPeerAllowedIps = it }, label = { Text(stringResource(R.string.allowed_ips)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wgPeerEndpoint, { wgPeerEndpoint = it }, label = { Text(stringResource(R.string.endpoint_optional)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("vpn.wireguard.set_peer", JsonObject().put("interface", wgName).put("name", wgPeerName).put("public_key", wgPeerPublicKey).put("preshared_key", wgPeerPresharedKey).put("allowed_ips", JsonArray(listOf(wgPeerAllowedIps))).put("endpoint", wgPeerEndpoint).put("persistent_keepalive", 25).put("route_allowed_ips", true), genericCommandQueued) }, Modifier.align(Alignment.End), enabled = wgPeerName.isNotBlank() && wgPeerPublicKey.isNotBlank())
            ActionRow {
                TextButton({ pendingCommand = PendingSafeCommand("vpn.wireguard.export_peer", JsonObject().put("interface", wgName).put("name", wgPeerName), genericCommandQueued) }, enabled = wgPeerName.isNotBlank()) { Text(stringResource(R.string.export)) }
                TextButton({ pendingCommand = PendingSafeCommand("vpn.wireguard.delete_peer", JsonObject().put("interface", wgName).put("name", wgPeerName), genericCommandQueued) }, enabled = wgPeerName.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
    }
    if (mode == NetworkScreenMode.Vpn && capabilities["vpn.openvpn.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.openvpn_client), openVpnName) {
            val openVpnClients = vpn?.optJsonObject("openvpn")?.optJsonArray("clients") ?: JsonArray()
            for (index in 0 until openVpnClients.length()) {
                val item = openVpnClients.optJsonObject(index) ?: continue
                val name = item.optString("name")
                val isEnabled = item.optBoolean("enabled")
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(name, style = MaterialTheme.typography.titleSmall)
                        Text(
                            if (item.optBoolean("runtime")) stringResource(R.string.connected) else if (isEnabled) stringResource(R.string.enabled_value) else stringResource(R.string.disabled_value),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    TextButton({ pendingCommand = PendingSafeCommand("vpn.openvpn.set_enabled", JsonObject().put("name", name).put("enabled", !isEnabled), genericCommandQueued) }) {
                        Text(stringResource(if (isEnabled) R.string.disable_action else R.string.enable_action))
                    }
                    if (item.optBoolean("export_available")) {
                        TextButton({ pendingCommand = PendingSafeCommand("vpn.openvpn.export_client", JsonObject().put("name", name), genericCommandQueued) }) { Text(stringResource(R.string.export)) }
                    }
                }
                if (index < openVpnClients.length() - 1) HorizontalDivider()
            }
            OutlinedTextField(openVpnName, { openVpnName = it }, label = { Text(stringResource(R.string.profile_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(openVpnConfig, { openVpnConfig = it }, label = { Text(stringResource(R.string.openvpn_config)) }, modifier = Modifier.fillMaxWidth(), minLines = 6)
            ActionRow {
                PrimaryActionButton(stringResource(R.string.import_profile), { pendingCommand = PendingSafeCommand("vpn.openvpn.set_client", JsonObject().put("name", openVpnName).put("enabled", true).put("config", openVpnConfig), genericCommandQueued) }, enabled = openVpnName.isNotBlank() && openVpnConfig.isNotBlank())
                TextButton({ pendingCommand = PendingSafeCommand("vpn.openvpn.delete_client", JsonObject().put("name", openVpnName), genericCommandQueued) }, enabled = openVpnName.isNotBlank()) { Text(stringResource(R.string.delete)) }
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
                PrimaryActionButton(stringResource(R.string.save), { pendingCommand = PendingSafeCommand("vpn.policy.set", JsonObject().put("name", vpnPolicyName).put("enabled", true).put("interface", vpnPolicyInterface).put("source", vpnPolicySource).put("destination", vpnPolicyDestination).put("protocol", "all"), genericCommandQueued) }, enabled = vpnPolicyName.isNotBlank() && vpnPolicyInterface.isNotBlank() && (vpnPolicySource.isNotBlank() || vpnPolicyDestination.isNotBlank()))
                TextButton({ pendingCommand = PendingSafeCommand("vpn.policy.delete", JsonObject().put("name", vpnPolicyName), genericCommandQueued) }, enabled = vpnPolicyName.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
    }
    if (mode == NetworkScreenMode.Internet) {
        NetworkMaintenanceCard(
            capabilities = capabilities,
            interfaceName = interfaceName,
            interfaceOptions = interfaceOptions,
            onInterfaceChange = { interfaceName = it },
            onCommand = { pendingCommand = it },
        )
    }
    MessageBanner(message, error = messageIsError)
    pendingCommand?.let { command -> SafeCommandDialog(
        repository, device.id, command,
        onDismiss = { pendingCommand = null },
        onApply = {
            pendingCommand = null
            queue(command.type, command.payload, command.successMessage)
        },
        onSessionExpired = onSessionExpired,
    ) }
}
