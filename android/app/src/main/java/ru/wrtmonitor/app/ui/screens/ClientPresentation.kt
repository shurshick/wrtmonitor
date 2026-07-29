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

internal fun JsonArray?.jsonObjects(): List<JsonObject> = this?.let { array ->
    (0 until array.length()).mapNotNull(array::optJsonObject)
}.orEmpty()

internal fun JsonArray?.jsonStrings(): List<String> = this?.let { array ->
    (0 until array.length()).mapNotNull { index -> array.optString(index).takeIf(String::isNotBlank) }
}.orEmpty()

internal fun String.toJsonArray(): JsonArray = JsonArray().also { array ->
    split(',').map(String::trim).filter(String::isNotBlank).forEach(array::put)
}

@Composable
internal fun ClientBackRow(onBack: () -> Unit, label: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = onBack) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = label)
        }
        Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
    }
}

internal fun clientGroupKey(client: NetworkClientDto): String = when {
    client.presenceState == "offline" -> "offline"
    client.presenceState == "recent" -> "recent"
    client.connectionType == "wifi" -> "wifi:${client.wifiSsid.orEmpty().ifBlank { "wifi" }}"
    client.connectionType == "wired" -> "wired"
    else -> "network"
}

@Composable
internal fun clientGroupTitle(key: String, clients: List<NetworkClientDto>): String = when {
    key == "offline" -> stringResource(R.string.offline_clients)
    key == "recent" -> stringResource(R.string.recent_clients)
    key == "wired" -> stringResource(R.string.wired_clients)
    key.startsWith("wifi:") -> clients.firstOrNull()?.wifiSsid?.takeIf(String::isNotBlank) ?: stringResource(R.string.wifi_clients)
    else -> stringResource(R.string.home_network)
}

@Composable
internal fun clientGroupSubtitle(clients: List<NetworkClientDto>): String {
    val online = clients.count(NetworkClientDto::online)
    val bandResources = clients.filter(NetworkClientDto::online).mapNotNull { wifiBandResource(it.wifiBand) }.distinct()
    val bands = mutableListOf<String>()
    for (resource in bandResources) bands += stringResource(resource)
    val connection = bands.takeIf { it.isNotEmpty() }?.joinToString(" · ")
    return listOfNotNull(connection, stringResource(R.string.client_segment_summary, clients.size, online)).joinToString(" · ")
}

@Composable
internal fun clientDisplayName(client: NetworkClientDto): String = clientDisplayNameRaw(client)
    .ifBlank { stringResource(R.string.client_unknown) }

internal fun clientDisplayNameRaw(client: NetworkClientDto): String {
    val candidate = client.displayName?.trim()?.takeUnless { it.isBlank() }
        ?: client.hostname?.trim()?.takeUnless { it.isBlank() }
        ?: ""
    return candidate.takeUnless(::looksLikeAddress).orEmpty()
}

internal fun looksLikeAddress(value: String): Boolean = value.contains(":") ||
    Regex("^\\d{1,3}(?:\\.\\d{1,3}){3}$").matches(value)

internal fun compactMac(mac: String): String = mac.lowercase(Locale.ROOT)

@Composable
internal fun presenceSourceLabel(source: String?): String? = when (source) {
    "wifi_station" -> stringResource(R.string.presence_wifi)
    "neighbour_active" -> stringResource(R.string.presence_neighbour)
    "traffic_activity" -> stringResource(R.string.presence_traffic)
    "neighbour_grace" -> stringResource(R.string.presence_grace)
    "confirmation_expired" -> stringResource(R.string.presence_expired)
    "neighbour_stale" -> stringResource(R.string.presence_stale)
    "neighbour_failed" -> stringResource(R.string.presence_failed)
    else -> null
}

@Composable
internal fun clientConnectionLabel(client: NetworkClientDto): String = when (client.connectionType) {
    "wifi" -> formatWifiBand(client.wifiBand) ?: stringResource(R.string.wifi)
    "wired" -> stringResource(R.string.client_connection_wired)
    else -> stringResource(R.string.client_connection_unknown)
}

@Composable
internal fun formatWifiBand(band: String?): String? {
    val resource = wifiBandResource(band) ?: return null
    return stringResource(resource)
}

internal fun wifiBandResource(band: String?): Int? = when (band?.lowercase(Locale.ROOT)) {
    "2g", "2.4g", "2.4ghz" -> R.string.client_band_2g
    "5g", "5ghz" -> R.string.client_band_5g
    "6g", "6ghz" -> R.string.client_band_6g
    else -> null
}

internal fun clientIcon(client: NetworkClientDto): ImageVector {
    val identity = listOfNotNull(client.displayName, client.hostname, client.vendor).joinToString(" ").lowercase(Locale.ROOT)
    return when {
        listOf("phone", "redmi", "poco", "xiaomi", "huawei", "mobile", "android", "iphone").any(identity::contains) -> Icons.Default.PhoneAndroid
        listOf("pc", "desktop", "computer", "laptop", "windows", "macbook").any(identity::contains) -> Icons.Default.Computer
        listOf("router", "openwrt", "gateway").any(identity::contains) -> Icons.Default.Router
        client.connectionType == "wifi" -> Icons.Default.Wifi
        else -> Icons.Default.DevicesOther
    }
}

internal fun formatClientBytes(value: Long): String = when {
    value >= 1024L * 1024 * 1024 -> String.format(Locale.getDefault(), "%.1f GB", value / (1024.0 * 1024 * 1024))
    value >= 1024L * 1024 -> String.format(Locale.getDefault(), "%.1f MB", value / (1024.0 * 1024))
    value >= 1024L -> String.format(Locale.getDefault(), "%.1f KB", value / 1024.0)
    else -> "$value B"
}

internal fun formatLinkRate(value: Long): String = when {
    value >= 1_000_000 -> String.format(Locale.getDefault(), "%.1f Gbit/s", value / 1_000_000.0)
    value >= 1_000 -> String.format(Locale.getDefault(), "%.0f Mbit/s", value / 1_000.0)
    else -> "$value Kbit/s"
}

internal fun formatClientDate(value: String?): String = runCatching {
    Instant.parse(value).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
}.getOrNull().orEmpty()
