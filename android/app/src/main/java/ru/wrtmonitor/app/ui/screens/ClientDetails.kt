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
internal fun ClientDetails(
    client: NetworkClientDto,
    profiles: List<ClientProfileDto>,
    canManagePolicy: Boolean,
    canSetLease: Boolean,
    canDeleteLease: Boolean,
    onBack: () -> Unit,
    onSave: (String, String, String?, JsonObject) -> Unit,
    onSetLease: (String, String) -> Unit,
    onDeleteLease: () -> Unit,
) {
    val policy = client.effectivePolicy
    val schedule = policy.optJsonObject("schedule") ?: JsonObject()
    val qos = policy.optJsonObject("qos") ?: JsonObject()
    val dnsPolicy = policy.optJsonObject("dns") ?: JsonObject()
    var displayName by remember(client.id, client.displayName) { mutableStateOf(client.displayName.orEmpty()) }
    var deviceType by remember(client.id, client.deviceType, client.deviceTypeSource) {
        mutableStateOf(
            if (client.deviceTypeSource == "user") client.deviceType else "unknown"
        )
    }
    var profileId by remember(client.id, client.profileId) { mutableStateOf(client.profileId) }
    var blocked by remember(client.id, policy.toString()) { mutableStateOf(policy.optBoolean("blocked")) }
    var scheduleEnabled by remember(client.id, schedule.toString()) { mutableStateOf(schedule.optBoolean("enabled")) }
    var weekdays by remember(client.id, schedule.toString()) {
        mutableStateOf(schedule.optJsonArray("weekdays")?.let { array ->
            (0 until array.length()).map(array::optString).filter(String::isNotBlank).toSet()
        } ?: emptySet())
    }
    var start by remember(client.id, schedule.toString()) { mutableStateOf(schedule.optString("start")) }
    var stop by remember(client.id, schedule.toString()) { mutableStateOf(schedule.optString("stop")) }
    var priority by remember(client.id, qos.toString()) { mutableStateOf(qos.optString("priority", "normal")) }
    var download by remember(client.id, qos.toString()) { mutableStateOf(qos.optInt("download_kbps").toString()) }
    var upload by remember(client.id, qos.toString()) { mutableStateOf(qos.optInt("upload_kbps").toString()) }
    var dnsProvider by remember(client.id, dnsPolicy.toString()) { mutableStateOf(dnsPolicy.optString("provider", "none")) }
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
            when (client.presenceState) {
                "online" -> stringResource(R.string.online)
                "recent" -> stringResource(R.string.client_recent)
                else -> stringResource(R.string.offline)
            },
            client.presenceState == "online",
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
        InfoRow(stringResource(R.string.last_confirmed), formatClientDate(client.lastConfirmedAt), stringResource(R.string.never_confirmed))
        InfoRow(stringResource(R.string.presence_source), presenceSourceLabel(client.presenceSource), stringResource(R.string.no_data))
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
                stringResource(R.string.client_device_type),
                deviceType,
                listOf(
                    SelectOption("unknown", stringResource(R.string.client_type_auto)),
                    SelectOption("phone", stringResource(R.string.client_type_phone)),
                    SelectOption("tablet", stringResource(R.string.client_type_tablet)),
                    SelectOption("computer", stringResource(R.string.client_type_computer)),
                    SelectOption("tv", stringResource(R.string.client_type_tv)),
                    SelectOption("speaker", stringResource(R.string.client_type_speaker)),
                    SelectOption("camera", stringResource(R.string.client_type_camera)),
                    SelectOption("printer", stringResource(R.string.client_type_printer)),
                    SelectOption("storage", stringResource(R.string.client_type_storage)),
                    SelectOption("router", stringResource(R.string.client_type_router)),
                    SelectOption("iot", stringResource(R.string.client_type_iot)),
                ),
                { deviceType = it },
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
            stringResource(R.string.client_dns_policy),
            stringResource(R.string.client_dns_policy_summary),
        ) {
            OptionSelector(
                stringResource(R.string.client_dns_policy),
                dnsProvider,
                listOf(
                    SelectOption("none", stringResource(R.string.client_dns_none)),
                    SelectOption("cloudflare-security", stringResource(R.string.client_dns_security)),
                    SelectOption("cloudflare-family", stringResource(R.string.client_dns_family)),
                ),
                { dnsProvider = it },
            )
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

    SectionCard(stringResource(R.string.client_activity)) {
        if (client.recentActivity.isEmpty()) {
            Text(
                stringResource(R.string.client_activity_empty),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            client.recentActivity.forEachIndexed { index, event ->
                InfoRow(
                    when (event.state) {
                        "online" -> stringResource(R.string.online)
                        "recent" -> stringResource(R.string.client_recent)
                        else -> stringResource(R.string.offline)
                    },
                    formatClientDate(event.occurredAt),
                    stringResource(R.string.no_data),
                )
                val details = listOfNotNull(
                    event.ipAddress,
                    event.networkInterface,
                ).joinToString(" · ")
                if (details.isNotBlank()) {
                    Text(
                        details,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (index < client.recentActivity.lastIndex) HorizontalDivider()
            }
        }
    }

    if (canManagePolicy) {
        PrimaryActionButton(
            label = stringResource(R.string.save_policy),
            onClick = {
                val days = JsonArray()
                weekdays.sorted().forEach(days::put)
                onSave(
                    displayName,
                    deviceType,
                    profileId,
                    JsonObject()
                        .put("blocked", blocked)
                        .put("schedule", JsonObject().put("enabled", scheduleEnabled).put("weekdays", days).put("start", start).put("stop", stop))
                        .put("qos", JsonObject().put("priority", priority).put("download_kbps", download.toIntOrNull() ?: 0).put("upload_kbps", upload.toIntOrNull() ?: 0))
                        .put("dns", JsonObject().put("provider", dnsProvider).put("blocked_domains", JsonArray())),
                )
            },
        )
    }
}
