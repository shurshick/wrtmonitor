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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.api.dto.JsonArray
import ru.wrtmonitor.app.api.dto.JsonObject
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
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

internal data class PendingSafeCommand(
    val type: String,
    val payload: JsonObject,
    val successMessage: String = "",
)

internal data class TimezoneOption(val zonename: String, val timezone: String, val label: String)

internal val timezoneOptions = listOf(
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

internal val netmaskOptions = (8..30).map { prefix ->
    val mask = (0xffffffffL shl (32 - prefix) and 0xffffffffL)
    SelectOption(
        value = listOf(24, 16, 8, 0).joinToString(".") { shift -> ((mask shr shift) and 0xff).toString() },
        label = "/$prefix · " + listOf(24, 16, 8, 0).joinToString(".") { shift -> ((mask shr shift) and 0xff).toString() },
    )
}

internal val weekdayOptions = listOf("mon", "tue", "wed", "thu", "fri", "sat", "sun").map { SelectOption(it, it.uppercase()) }
internal val priorityOptions = listOf("low", "normal", "high", "realtime").map { SelectOption(it, it) }
internal val leaseTimeOptions = listOf("30m", "1h", "6h", "12h", "24h", "72h", "168h").map { SelectOption(it, it) }
internal val wanProtocolOptions = listOf("dhcp", "static", "pppoe").map { SelectOption(it, it.uppercase()) }
internal val encryptedDnsProviderOptions = listOf(
    SelectOption("cloudflare", "Cloudflare"),
    SelectOption("quad9", "Quad9"),
    SelectOption("google", "Google"),
)
internal val wifiCountryOptions = listOf("RU", "BY", "KZ", "AM", "AZ", "GE", "KG", "UZ", "DE", "FR", "GB", "IT", "ES", "PL", "NL", "FI", "SE", "NO", "US", "CA", "CN", "JP", "KR", "AU").map { SelectOption(it, it) }
internal val wifiChannelOptions = (
    listOf("auto") + (1..14).map(Int::toString) +
        listOf("36", "40", "44", "48", "52", "56", "60", "64", "100", "104", "108", "112", "116", "120", "124", "128", "132", "136", "140", "144", "149", "153", "157", "161", "165")
    ).map { SelectOption(it, if (it == "auto") "AUTO" else it) }
internal fun wifiChannelOptionsForBand(band: String): List<SelectOption> {
    val values = when (band.lowercase()) {
        "2g" -> listOf("auto") + (1..13).map(Int::toString)
        "5g" -> listOf("auto", "36", "40", "44", "48", "52", "56", "60", "64", "100", "104", "108", "112", "116", "120", "124", "128", "132", "136", "140", "144", "149", "153", "157", "161", "165")
        else -> wifiChannelOptions.map(SelectOption::value)
    }
    return values.map { SelectOption(it, if (it == "auto") "AUTO" else it) }
}
internal val wifiModeOptions = listOf("HE80", "HE40", "HE20", "VHT160", "VHT80", "VHT40", "VHT20", "HT40", "HT20").map { SelectOption(it, it) }
internal val wifiEncryptionOptions = listOf("sae-mixed", "sae", "psk2", "none").map { SelectOption(it, it) }
internal val processSignalOptions = listOf("TERM", "HUP", "INT", "KILL").map { SelectOption(it, it) }
internal val firewallPolicyOptions = listOf("ACCEPT", "REJECT", "DROP").map { SelectOption(it, it) }
internal val firewallProtocolOptions = listOf("tcpudp", "tcp", "udp", "icmp", "all").map { SelectOption(it, it.uppercase()) }

internal fun encryptedDnsProviderFromValue(value: String): String = when {
    value.contains("quad9", ignoreCase = true) -> "quad9"
    value.contains("google", ignoreCase = true) -> "google"
    else -> "cloudflare"
}

@Composable
internal fun SafeCommandDialog(
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

internal fun firstRadio(telemetry: TelemetryDto?): JsonObject? =
    telemetry?.wifi?.optJsonArray("radios")?.optJsonObject(0)
        ?: telemetry?.payload?.optJsonObject("wifi")?.optJsonArray("radios")?.optJsonObject(0)

internal fun firstInterface(telemetry: TelemetryDto?): JsonObject? =
    firstRadio(telemetry)?.optJsonArray("interfaces")?.optJsonObject(0)

internal fun findRadio(radios: JsonArray, radioId: String): JsonObject? =
    (0 until radios.length()).mapNotNull(radios::optJsonObject)
        .firstOrNull { it.optString("id") == radioId }

internal fun findInterface(interfaces: JsonArray, interfaceId: String): JsonObject? =
    (0 until interfaces.length()).mapNotNull(interfaces::optJsonObject)
        .firstOrNull { it.optString("id") == interfaceId }

internal fun formatMicroseconds(value: Long): String = when {
    value >= 1_000_000 -> String.format(Locale.getDefault(), "%.2f s", value / 1_000_000.0)
    value >= 1_000 -> String.format(Locale.getDefault(), "%.1f ms", value / 1_000.0)
    else -> "$value us"
}

@Composable
internal fun formatRouterDuration(seconds: Long): String {
    val days = seconds / 86_400
    val hours = (seconds % 86_400) / 3_600
    val minutes = (seconds % 3_600) / 60
    return listOfNotNull(
        days.takeIf { it > 0 }?.let { stringResource(R.string.duration_days_short, it.toInt()) },
        hours.takeIf { it > 0 }?.let { stringResource(R.string.duration_hours_short, it.toInt()) },
        stringResource(R.string.duration_minutes_short, minutes.toInt()),
    ).joinToString(" ")
}
