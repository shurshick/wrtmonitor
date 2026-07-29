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
internal fun ClientsList(
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
    val recentCount = clients.count { it.presenceState == "recent" }
    val offlineCount = clients.size - onlineCount - recentCount
    val query = search.trim().lowercase(Locale.getDefault())
    val filtered = clients.filter { client ->
        val stateMatches = when (filter) {
            ClientsFilter.All -> true
            ClientsFilter.Online -> client.presenceState == "online"
            ClientsFilter.Recent -> client.presenceState == "recent"
            ClientsFilter.Offline -> client.presenceState == "offline"
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
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
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
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(
                selected = filter == ClientsFilter.Recent,
                onClick = { onFilterChange(ClientsFilter.Recent) },
                modifier = Modifier.weight(1f),
                label = { Text(stringResource(R.string.client_filter_recent, recentCount), maxLines = 1, overflow = TextOverflow.Ellipsis) },
            )
            FilterChip(
                selected = filter == ClientsFilter.Offline,
                onClick = { onFilterChange(ClientsFilter.Offline) },
                modifier = Modifier.weight(1f),
                label = { Text(stringResource(R.string.client_filter_offline, offlineCount), maxLines = 1, overflow = TextOverflow.Ellipsis) },
            )
        }
    }

    if (filtered.isEmpty()) {
        SectionCard(stringResource(R.string.home_network_clients)) {
            Text(stringResource(R.string.client_filter_empty), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }

    val groups = filtered.groupBy(::clientGroupKey).toList().sortedWith(
        compareBy<Pair<String, List<NetworkClientDto>>> { when (it.first) { "recent" -> 1; "offline" -> 2; else -> 0 } }
            .thenBy { it.first.lowercase(Locale.getDefault()) },
    )
    groups.forEach { (key, groupClients) ->
        ClientGroup(
            title = clientGroupTitle(key, groupClients),
            subtitle = clientGroupSubtitle(groupClients),
            initiallyExpanded = key != "offline",
            forceExpanded = query.isNotBlank() || filter != ClientsFilter.All,
            clients = groupClients.sortedWith(
                compareBy<NetworkClientDto> {
                    when (it.presenceState) {
                        "online" -> 0
                        "recent" -> 1
                        else -> 2
                    }
                }
                    .thenBy { clientDisplayNameRaw(it).lowercase(Locale.getDefault()) },
            ),
            onOpenClient = onOpenClient,
        )
    }
}
@Composable
internal fun ClientGroup(
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
internal fun ClientRow(client: NetworkClientDto, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 14.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(38.dp).background(
                if (client.presenceState == "online") MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                CircleShape,
            ),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                clientIcon(client),
                contentDescription = null,
                modifier = Modifier.size(21.dp),
                tint = when (client.presenceState) {
                    "online" -> MaterialTheme.colorScheme.secondary
                    "recent" -> MaterialTheme.colorScheme.tertiary
                    else -> MaterialTheme.colorScheme.outline
                },
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
                color = when (client.presenceState) {
                    "online" -> MaterialTheme.colorScheme.secondary
                    "recent" -> MaterialTheme.colorScheme.tertiary
                    else -> MaterialTheme.colorScheme.outline
                },
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
