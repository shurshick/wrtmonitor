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
import ru.wrtmonitor.app.api.dto.JsonArray
import ru.wrtmonitor.app.api.dto.JsonObject
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

@Composable
internal fun ClientsSettings(
    profiles: List<ClientProfileDto>,
    canManageProfiles: Boolean,
    canConfigureDhcp: Boolean,
    canConfigureIpv6: Boolean,
    topology: JsonObject?,
    canConfigureSegments: Boolean,
    canConfigureVlans: Boolean,
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
    ipv6Enabled: Boolean,
    onIpv6EnabledChange: (Boolean) -> Unit,
    ipv6Prefix: String,
    onIpv6PrefixChange: (String) -> Unit,
    ipv6Ra: String,
    onIpv6RaChange: (String) -> Unit,
    ipv6Dhcp: String,
    onIpv6DhcpChange: (String) -> Unit,
    ipv6Ndp: String,
    onIpv6NdpChange: (String) -> Unit,
    onBack: () -> Unit,
    onCreateProfile: () -> Unit,
    onDeleteProfile: (String) -> Unit,
    onSaveDhcp: () -> Unit,
    onSaveIpv6: () -> Unit,
    onPrepareCommand: (PendingSafeCommand) -> Unit,
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
    if (canConfigureIpv6) {
        val ipv6ModeOptions = listOf(
            SelectOption("server", stringResource(R.string.ipv6_mode_server)),
            SelectOption("relay", stringResource(R.string.ipv6_mode_relay)),
            SelectOption("hybrid", stringResource(R.string.ipv6_mode_hybrid)),
            SelectOption("disabled", stringResource(R.string.disabled_value)),
        )
        ExpandableSettingsCard(
            title = stringResource(R.string.ipv6_settings),
            summary = if (ipv6Enabled) "/$ipv6Prefix · RA $ipv6Ra · DHCPv6 $ipv6Dhcp" else stringResource(R.string.disabled_value),
        ) {
            SwitchSettingRow(stringResource(R.string.ipv6_lan_enabled), checked = ipv6Enabled, onCheckedChange = onIpv6EnabledChange)
            OptionSelector(stringResource(R.string.prefix_length), ipv6Prefix, clientIpv6PrefixOptions, onIpv6PrefixChange)
            OptionSelector(stringResource(R.string.ipv6_ra_mode), ipv6Ra, ipv6ModeOptions, onIpv6RaChange)
            OptionSelector(stringResource(R.string.ipv6_dhcp_mode), ipv6Dhcp, ipv6ModeOptions, onIpv6DhcpChange)
            OptionSelector(stringResource(R.string.ipv6_ndp_mode), ipv6Ndp, ipv6ModeOptions.filter { it.value != "server" }, onIpv6NdpChange)
            PrimaryActionButton(stringResource(R.string.save_ipv6), onSaveIpv6)
        }
    }
    if (canConfigureSegments || canConfigureVlans) {
        NetworkTopologySettings(
            topology = topology,
            canConfigureSegments = canConfigureSegments,
            canConfigureVlans = canConfigureVlans,
            onPrepareCommand = onPrepareCommand,
        )
    }
}
@Composable
internal fun NetworkTopologySettings(
    topology: JsonObject?,
    canConfigureSegments: Boolean,
    canConfigureVlans: Boolean,
    onPrepareCommand: (PendingSafeCommand) -> Unit,
) {
    val topologyKey = topology?.toString().orEmpty()
    val segments = remember(topologyKey) {
        topology?.optJsonArray("segments").jsonObjects()
            .filterNot { it.optString("name") in setOf("wan", "wan6", "loopback") }
    }
    val bridges = remember(topologyKey) { topology?.optJsonArray("bridges").jsonObjects() }
    val vlans = remember(topologyKey) { topology?.optJsonArray("vlans").jsonObjects() }
    val queued = stringResource(R.string.command_queued)

    if (canConfigureSegments) {
        val segmentChoices = listOf(SelectOption("__new__", stringResource(R.string.network_segment_new))) +
            segments.map { SelectOption(it.optString("name"), it.optString("name")) }
        var selectedName by remember(topologyKey) { mutableStateOf(segments.firstOrNull()?.optString("name") ?: "__new__") }
        val selected = segments.firstOrNull { it.optString("name") == selectedName }
        val selectedBridge = bridges.firstOrNull { it.optString("name") == selected?.optString("device") }
        var name by remember(selectedName, topologyKey) { mutableStateOf(selected?.optString("name").orEmpty()) }
        var address by remember(selectedName, topologyKey) { mutableStateOf(selected?.optString("ip_address").orEmpty()) }
        var netmask by remember(selectedName, topologyKey) { mutableStateOf(selected?.optString("netmask").orEmpty().ifBlank { "255.255.255.0" }) }
        var deviceName by remember(selectedName, topologyKey) { mutableStateOf(selected?.optString("device").orEmpty()) }
        var ports by remember(selectedName, topologyKey) { mutableStateOf(selectedBridge?.optJsonArray("ports").jsonStrings().joinToString(", ")) }
        var enabled by remember(selectedName, topologyKey) { mutableStateOf(selected?.optBoolean("enabled", true) ?: true) }
        var bridgeEnabled by remember(selectedName, topologyKey) { mutableStateOf(selectedBridge != null || selected == null) }
        var dhcpEnabled by remember(selectedName, topologyKey) { mutableStateOf(selected?.optJsonObject("dhcp")?.optBoolean("enabled", false) ?: true) }
        var dhcpStart by remember(selectedName, topologyKey) { mutableStateOf(selected?.optJsonObject("dhcp")?.optString("start").orEmpty().ifBlank { "100" }) }
        var dhcpLimit by remember(selectedName, topologyKey) { mutableStateOf(selected?.optJsonObject("dhcp")?.optString("limit").orEmpty().ifBlank { "150" }) }
        var leaseTime by remember(selectedName, topologyKey) { mutableStateOf(selected?.optJsonObject("dhcp")?.optString("leasetime").orEmpty().ifBlank { "12h" }) }
        var policy by remember(selectedName, topologyKey) { mutableStateOf(selected?.optString("policy").orEmpty().ifBlank { if (selectedName == "lan") "trusted" else "guest" }) }

        ExpandableSettingsCard(
            title = stringResource(R.string.network_segments),
            summary = stringResource(R.string.network_segments_summary, segments.size),
        ) {
            OptionSelector(
                label = stringResource(R.string.network_segment),
                value = selectedName,
                options = segmentChoices,
                onValueChange = { selectedName = it },
            )
            OutlinedTextField(name, { name = it }, label = { Text(stringResource(R.string.system_name)) }, modifier = Modifier.fillMaxWidth(), enabled = selected == null, singleLine = true)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(address, { address = it }, label = { Text(stringResource(R.string.ipv4_address)) }, modifier = Modifier.weight(1f), singleLine = true)
                OutlinedTextField(netmask, { netmask = it }, label = { Text(stringResource(R.string.netmask)) }, modifier = Modifier.weight(1f), singleLine = true)
            }
            OutlinedTextField(deviceName, { deviceName = it }, label = { Text(stringResource(R.string.bridge_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(ports, { ports = it }, label = { Text(stringResource(R.string.bridge_ports)) }, modifier = Modifier.fillMaxWidth(), supportingText = { Text(stringResource(R.string.bridge_ports_hint)) }, singleLine = true)
            SwitchSettingRow(stringResource(R.string.enabled_value), checked = enabled, onCheckedChange = { enabled = it })
            SwitchSettingRow(stringResource(R.string.create_bridge), checked = bridgeEnabled, onCheckedChange = { bridgeEnabled = it })
            SwitchSettingRow(stringResource(R.string.dhcp_server), checked = dhcpEnabled, onCheckedChange = { dhcpEnabled = it })
            if (dhcpEnabled) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(dhcpStart, { dhcpStart = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.pool_start)) }, modifier = Modifier.weight(1f), singleLine = true)
                    OutlinedTextField(dhcpLimit, { dhcpLimit = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.pool_size)) }, modifier = Modifier.weight(1f), singleLine = true)
                }
                OptionSelector(
                    label = stringResource(R.string.lease_time),
                    value = leaseTime,
                    options = clientLeaseTimeOptions,
                    onValueChange = { leaseTime = it },
                )
            }
            OptionSelector(
                stringResource(R.string.segment_policy),
                policy,
                listOf(
                    SelectOption("trusted", stringResource(R.string.segment_policy_trusted)),
                    SelectOption("guest", stringResource(R.string.segment_policy_guest)),
                    SelectOption("isolated", stringResource(R.string.segment_policy_isolated)),
                ),
                onValueChange = { policy = it },
            )
            ActionRow {
                PrimaryActionButton(
                    stringResource(R.string.save),
                    onClick = {
                        onPrepareCommand(PendingSafeCommand(
                            "network.set_segment",
                            JsonObject()
                                .put("name", name).put("protocol", "static").put("device", deviceName)
                                .put("bridge_section", selectedBridge?.optString("section").orEmpty())
                                .put("ip_address", address).put("netmask", netmask).put("enabled", enabled)
                                .put("bridge", bridgeEnabled).put("ports", ports.toJsonArray())
                                .put("stp", selectedBridge?.optBoolean("stp", false) ?: false)
                                .put("igmp_snooping", selectedBridge?.optBoolean("igmp_snooping", true) ?: true)
                                .put("dhcp_enabled", dhcpEnabled).put("dhcp_start", dhcpStart.toIntOrNull() ?: 100)
                                .put("dhcp_limit", dhcpLimit.toIntOrNull() ?: 150).put("dhcp_leasetime", leaseTime)
                                .put("policy", policy),
                            queued,
                        ))
                    },
                    enabled = name.isNotBlank() && address.isNotBlank() && netmask.isNotBlank(),
                )
                if (selected != null && selectedName !in setOf("lan", "wan", "wan6", "loopback")) {
                    TextButton(onClick = { onPrepareCommand(PendingSafeCommand("network.delete_segment", JsonObject().put("name", selectedName), queued)) }) { Text(stringResource(R.string.delete)) }
                }
            }
        }
    }

    if (canConfigureVlans) {
        val vlanChoices = listOf(SelectOption("__new__", stringResource(R.string.vlan_new))) +
            vlans.map { SelectOption(it.optString("section"), "VLAN ${it.optInt("vlan_id")} · ${it.optString("device")}") }
        var selectedSection by remember(topologyKey) { mutableStateOf(vlans.firstOrNull()?.optString("section") ?: "__new__") }
        val selected = vlans.firstOrNull { it.optString("section") == selectedSection }
        var bridgeName by remember(selectedSection, topologyKey) { mutableStateOf(selected?.optString("device").orEmpty()) }
        var vlanId by remember(selectedSection, topologyKey) { mutableStateOf(selected?.optInt("vlan_id")?.toString().orEmpty()) }
        var vlanPorts by remember(selectedSection, topologyKey) { mutableStateOf(selected?.optJsonArray("ports").jsonStrings().joinToString(", ")) }
        ExpandableSettingsCard(
            title = stringResource(R.string.bridge_vlan),
            summary = stringResource(R.string.bridge_vlan_summary, vlans.size),
        ) {
            OptionSelector(
                label = stringResource(R.string.vlan),
                value = selectedSection,
                options = vlanChoices,
                onValueChange = { selectedSection = it },
            )
            val bridgeChoices = bridges.map { SelectOption(it.optString("name"), it.optString("name")) }
            if (bridgeChoices.isNotEmpty()) OptionSelector(
                label = stringResource(R.string.bridge_name),
                value = bridgeName,
                options = bridgeChoices,
                onValueChange = { bridgeName = it },
            )
            else OutlinedTextField(bridgeName, { bridgeName = it }, label = { Text(stringResource(R.string.bridge_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(vlanId, { vlanId = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.vlan_id)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(vlanPorts, { vlanPorts = it }, label = { Text(stringResource(R.string.bridge_ports)) }, modifier = Modifier.fillMaxWidth(), supportingText = { Text(stringResource(R.string.vlan_ports_hint)) }, singleLine = true)
            ActionRow {
                PrimaryActionButton(
                    stringResource(R.string.save),
                    onClick = { onPrepareCommand(PendingSafeCommand("network.set_vlan", JsonObject().put("section", selected?.optString("section").orEmpty()).put("device", bridgeName).put("vlan_id", vlanId.toIntOrNull() ?: 1).put("ports", vlanPorts.toJsonArray()), queued)) },
                    enabled = bridgeName.isNotBlank() && vlanId.toIntOrNull() in 1..4094 && vlanPorts.isNotBlank(),
                )
                if (selected != null) TextButton(onClick = { onPrepareCommand(PendingSafeCommand("network.delete_vlan", JsonObject().put("section", selectedSection), queued)) }) { Text(stringResource(R.string.delete)) }
            }
        }
    }
}
