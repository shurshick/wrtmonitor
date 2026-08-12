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
import androidx.compose.foundation.Image
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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
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
import ru.wrtmonitor.app.api.dto.WifiExperienceDto
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
import android.graphics.Bitmap
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter

@Composable
fun WifiControlScreen(serverUrl: String, accessToken: String, device: DeviceDto, onSessionExpired: () -> Unit) {
    val scope = rememberCoroutineScope()
    val repository = remember(serverUrl, accessToken) { RouterRepository(serverUrl, accessToken) }
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var wifiExperience by remember { mutableStateOf<WifiExperienceDto?>(null) }
    var managementOptions by remember { mutableStateOf<ManagementOptionsDto?>(null) }
    var loading by remember { mutableStateOf(true) }
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
    var selectedRadioId by rememberSaveable(device.id) { mutableStateOf("") }
    var selectedInterfaceId by rememberSaveable(device.id) { mutableStateOf("") }
    var interfaceEnabled by remember { mutableStateOf(true) }
    var interfaceHidden by remember { mutableStateOf(false) }
    var interfaceIsolated by remember { mutableStateOf(false) }
    var interfaceEncryption by remember { mutableStateOf("sae-mixed") }
    var roamingR by remember { mutableStateOf(false) }
    var roamingK by remember { mutableStateOf(false) }
    var roamingV by remember { mutableStateOf(false) }
    var mobilityDomain by remember { mutableStateOf("") }
    var wifiQr by remember { mutableStateOf<Pair<String, Bitmap>?>(null) }

    val refresh: () -> Unit = {
        scope.launch {
            loading = true
            when (val result = repository.latestTelemetry(device.id)) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    if (selectedRadioId.isBlank()) selectedRadioId = firstRadio(result.data)?.optString("id").orEmpty()
                }
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                    message = result.message
                    messageIsError = true
                }
            }
            when (val result = repository.wifi(device.id)) {
                is ApiResult.Success -> wifiExperience = result.data
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

    fun queue(type: String, payload: JsonObject, success: String) {
        scope.launch {
            when (val result = repository.createCommand(device.id, type, payload, confirmed = true)) {
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
    val wifi = telemetry?.wifi ?: telemetry?.payload?.optJsonObject("wifi")
    val capabilities = telemetry?.agent?.capabilities ?: emptyMap()
    val wifiSsidQueued = stringResource(R.string.wifi_ssid_queued)
    val wifiPasswordQueued = stringResource(R.string.wifi_password_queued)
    val wifiToggleQueued = stringResource(R.string.wifi_toggle_queued)
    val wifiChannelQueued = stringResource(R.string.wifi_channel_queued)
    val wifiCountryQueued = stringResource(R.string.wifi_country_queued)

    val radios = wifi?.optJsonArray("radios") ?: JsonArray()
    val radio = findRadio(radios, selectedRadioId) ?: radios.optJsonObject(0)
    val radioId = radio?.optString("id").takeUnless { it.isNullOrBlank() } ?: "radio0"
    val interfaces = radio?.optJsonArray("interfaces") ?: JsonArray()
    val iface = findInterface(interfaces, selectedInterfaceId) ?: interfaces.optJsonObject(0)
    val ifaceId = iface?.optString("id").takeUnless { it.isNullOrBlank() }
    val radioOptions = (0 until radios.length()).mapNotNull(radios::optJsonObject).mapIndexed { index, item ->
        val id = item.optString("id").ifBlank { "radio$index" }
        SelectOption(id, listOf(item.optString("band"), item.optString("name").ifBlank { id }).filter(String::isNotBlank).joinToString(" · "))
    }
    val interfaceOptions = (0 until interfaces.length()).mapNotNull(interfaces::optJsonObject).map { item ->
        val id = item.optString("id")
        SelectOption(id, item.optString("ssid").ifBlank { id })
    }
    val networkOptions = telemetry?.network?.optJsonArray("interfaces")?.let { array ->
        (0 until array.length()).mapNotNull(array::optJsonObject)
            .map { it.optString("interface") }.filter(String::isNotBlank).distinct()
            .map { SelectOption(it, it) }
    }.orEmpty()
    val observedRadioOptions = managementOptions?.wifiRadios?.firstOrNull { it.id == radioId }
    val routerChannelOptions = observedRadioOptions?.supportedChannels.orEmpty().ifEmpty {
        managementOptions?.fallbackWifiChannels.orEmpty()
    }.map { SelectOption(it, if (it == "auto") "AUTO" else it) }.ifEmpty {
        listOf(SelectOption(channel.ifBlank { "auto" }, channel.ifBlank { "AUTO" }))
    }
    val routerCountryOptions = managementOptions?.wifiCountries.orEmpty().map {
        SelectOption(it.value, it.label)
    }.ifEmpty { listOf(SelectOption(country, country)) }
    LaunchedEffect(telemetry, selectedRadioId) {
        val selected = findRadio(radios, selectedRadioId) ?: radios.optJsonObject(0) ?: return@LaunchedEffect
        if (selectedRadioId != selected.optString("id")) selectedRadioId = selected.optString("id")
        enabled = selected.optBoolean("up", true)
        channel = selected.optString("channel").ifBlank { "auto" }
        country = selected.optString("country")
        htmode = selected.optString("htmode")
        txpower = selected.optString("txpower")
        val selectedIface = selected.optJsonArray("interfaces")?.optJsonObject(0)
        selectedInterfaceId = selectedIface?.optString("id").orEmpty()
        ssid = selectedIface?.optString("ssid").orEmpty()
        newNetwork = selectedIface?.optString("network").orEmpty()
        val schedule = selected.optJsonObject("schedule")
        scheduleEnabled = schedule?.optBoolean("enabled") ?: false
        scheduleDays = schedule?.optJsonArray("weekdays")?.let { array ->
            (0 until array.length()).map { array.optString(it) }.filter(String::isNotBlank).toSet()
        } ?: scheduleDays
        scheduleStart = schedule?.optString("start").orEmpty().ifBlank { scheduleStart }
        scheduleStop = schedule?.optString("stop").orEmpty().ifBlank { scheduleStop }
    }
    LaunchedEffect(selectedInterfaceId) {
        val selected = findInterface(interfaces, selectedInterfaceId) ?: return@LaunchedEffect
        ssid = selected.optString("ssid")
        newNetwork = selected.optString("network")
        interfaceEnabled = selected.optBoolean("enabled", true)
        interfaceHidden = selected.optBoolean("hidden", false)
        interfaceIsolated = selected.optBoolean("isolate", false)
        interfaceEncryption = selected.optString("encryption").ifBlank { "sae-mixed" }
        roamingR = selected.optBoolean("ieee80211r", false)
        roamingK = selected.optBoolean("ieee80211k", false)
        roamingV = selected.optBoolean("bss_transition", false)
        mobilityDomain = selected.optString("mobility_domain")
    }
    RouterPageHeader(
        title = stringResource(R.string.wifi),
        subtitle = stringResource(R.string.wifi_screen_summary),
        onRefresh = refresh,
    )
    if (wifiExperience?.state == "unsupported") {
        SectionCard(
            title = stringResource(R.string.wifi_unavailable),
            subtitle = stringResource(R.string.wifi_no_radio_explanation),
        ) {
            Text(stringResource(R.string.wifi_no_empty_controls), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        MessageBanner(message, error = messageIsError)
        return
    }
    if (radioOptions.isNotEmpty()) {
        SectionCard(title = stringResource(R.string.wifi_selected_radio), subtitle = radio?.optString("name").orEmpty()) {
            OptionSelector(stringResource(R.string.wifi_radio), selectedRadioId, radioOptions, { selectedRadioId = it })
            val selectedSurvey = radio?.optJsonObject("survey")
            if (selectedSurvey?.optString("state") == "observed") {
                val surveyDetails = listOfNotNull(
                    selectedSurvey.optInt("utilization_percent").takeIf { !selectedSurvey.isNull("utilization_percent") }?.let { stringResource(R.string.wifi_air_utilization, it) },
                    selectedSurvey.optInt("noise_dbm").takeIf { !selectedSurvey.isNull("noise_dbm") }?.let { stringResource(R.string.wifi_noise, it) },
                ).joinToString(" · ")
                if (surveyDetails.isNotBlank()) Text(surveyDetails, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                Text(stringResource(R.string.wifi_survey_unsupported), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
    SectionCard(
        title = stringResource(R.string.wifi_status),
        subtitle = stringResource(R.string.radio_count_value, radios.length()),
    ) {
        when {
            loading && telemetry == null -> CircularProgressIndicator(Modifier.size(24.dp))
            telemetry?.dataState?.kind == "unsupported" -> Text(stringResource(R.string.unsupported_data), color = MaterialTheme.colorScheme.onSurfaceVariant)
            telemetry?.dataState?.kind == "error" -> Text(telemetry?.dataState?.reason ?: stringResource(R.string.data_error), color = MaterialTheme.colorScheme.error)
            telemetry?.isStale == true -> Text(stringResource(R.string.stale_telemetry), color = MaterialTheme.colorScheme.tertiary)
        }
        if (wifi?.optBoolean("available", false) != true || radios.length() == 0) {
            Text(stringResource(R.string.wifi_unavailable), color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            for (index in 0 until radios.length()) {
                val item = radios.optJsonObject(index) ?: continue
                val radioName = item.optString("id").ifBlank { "radio$index" }
                val survey = item.optJsonObject("survey")
                val details = listOfNotNull(
                    item.optString("band").takeIf(String::isNotBlank),
                    item.optString("channel").takeIf(String::isNotBlank)?.let { stringResource(R.string.channel_value, it) },
                    item.optString("country").takeIf(String::isNotBlank),
                    survey?.optInt("utilization_percent")?.takeIf { !survey.isNull("utilization_percent") }?.let { stringResource(R.string.wifi_air_utilization, it) },
                    survey?.optInt("noise_dbm")?.takeIf { !survey.isNull("noise_dbm") }?.let { stringResource(R.string.wifi_noise, it) },
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
        if (capabilities["wifi.read"] == true) {
            TonalActionButton(
                stringResource(R.string.refresh),
                { pendingCommand = PendingSafeCommand("wifi.status", JsonObject(), wifiToggleQueued) },
            )
        }
    }

    if (capabilities["wifi.manage_ssid"] == true) {
        SectionCard(title = stringResource(R.string.wifi_networks), subtitle = stringResource(R.string.radio_count_value, interfaces.length())) {
            wifiExperience?.networks?.filter { it.radioId == radioId }?.forEachIndexed { index, networkItem ->
                val networkId = networkItem.id
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(networkItem.ssid.ifBlank { networkId }, style = MaterialTheme.typography.titleSmall)
                        Text(
                            listOf(
                                networkItem.band,
                                networkItem.network,
                                networkItem.encryption,
                                stringResource(R.string.wifi_clients_count, networkItem.stationCount),
                            ).filter(String::isNotBlank).joinToString(" · "),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (capabilities["wifi.qr"] == true && networkItem.enabled) {
                        TonalActionButton(stringResource(R.string.wifi_show_qr), {
                            scope.launch {
                                when (val result = repository.wifiQr(device.id, networkId)) {
                                    is ApiResult.Success -> wifiQr = result.data.ssid to createWifiQrBitmap(result.data.wifiUri)
                                    is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else {
                                        message = result.message; messageIsError = true
                                    }
                                }
                            }
                        })
                    }
                    SecondaryActionButton(
                        label = stringResource(R.string.wifi_delete_network),
                        onClick = { pendingCommand = PendingSafeCommand("wifi.delete_ssid", JsonObject().put("iface", networkId), wifiToggleQueued) },
                    )
                }
                if (index < (wifiExperience?.networks?.count { it.radioId == radioId } ?: 0) - 1) HorizontalDivider()
            }
        }
        ExpandableSettingsCard(title = stringResource(R.string.wifi_add_network), summary = newSsid) {
            OutlinedTextField(newSsid, { newSsid = it }, label = { Text("SSID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OptionSelector(stringResource(R.string.wifi_network_name), newNetwork, networkOptions, { newNetwork = it })
            OptionSelector(stringResource(R.string.wifi_encryption), newEncryption, wifiEncryptionOptions, { newEncryption = it })
            OutlinedTextField(newPassword, { newPassword = it }, label = { Text(stringResource(R.string.wifi_password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
            PrimaryActionButton(
                label = stringResource(R.string.wifi_add_network),
                onClick = { pendingCommand = PendingSafeCommand("wifi.add_ssid", JsonObject().put("radio", radioId).put("ssid", newSsid).put("network", newNetwork).put("encryption", newEncryption).put("key", newPassword).put("hidden", false).put("isolate", false), wifiToggleQueued) },
                enabled = newSsid.isNotBlank() && newNetwork.isNotBlank() && (newEncryption == "none" || newPassword.length >= 8),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }

    if (capabilities["wifi.radio.configure"] == true) {
        ExpandableSettingsCard(title = stringResource(R.string.wifi_radio_advanced), summary = listOf(channel, htmode, country).filter(String::isNotBlank).joinToString(" · ")) {
            SwitchSettingRow(stringResource(R.string.wifi_state), checked = enabled, onCheckedChange = { enabled = it })
            OptionSelector(stringResource(R.string.wifi_channel), channel, routerChannelOptions, { channel = it })
            OptionSelector(stringResource(R.string.wifi_width_mode), htmode, wifiModeOptions, { htmode = it })
            OptionSelector(stringResource(R.string.wifi_country), country, routerCountryOptions, { country = it })
            OutlinedTextField(txpower, { txpower = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.wifi_txpower)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(label = stringResource(R.string.save), onClick = {
                val payload = JsonObject().put("radio", radioId).put("enabled", enabled).put("channel", channel).put("htmode", htmode).put("country", country)
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
            PrimaryActionButton(label = stringResource(R.string.save), onClick = { pendingCommand = PendingSafeCommand("wifi.set_schedule", JsonObject().put("radio", radioId).put("enabled", scheduleEnabled).put("weekdays", JsonArray(scheduleDays.sorted())).put("start", scheduleStart).put("stop", scheduleStop), wifiToggleQueued) }, modifier = Modifier.align(Alignment.End))
        }
    }

    if (capabilities["wifi.mesh"] == true) {
        ExpandableSettingsCard(title = stringResource(R.string.wifi_mesh), summary = meshId) {
            SwitchSettingRow(stringResource(R.string.wifi_state), checked = meshEnabled, onCheckedChange = { meshEnabled = it })
            OutlinedTextField(meshId, { meshId = it }, label = { Text(stringResource(R.string.wifi_mesh_id)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(meshPassword, { meshPassword = it }, label = { Text(stringResource(R.string.wifi_password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
            PrimaryActionButton(label = stringResource(R.string.save), onClick = { pendingCommand = PendingSafeCommand("wifi.set_mesh", JsonObject().put("radio", radioId).put("enabled", meshEnabled).put("mesh_id", meshId).put("network", "lan").put("encryption", "sae").put("key", meshPassword), wifiToggleQueued) }, enabled = !meshEnabled || (meshId.isNotBlank() && meshPassword.length >= 8), modifier = Modifier.align(Alignment.End))
        }
    }

    val stationGroups = wifi?.optJsonArray("stations") ?: JsonArray()
    if (stationGroups.length() > 0) {
        SectionCard(title = stringResource(R.string.wifi_stations)) {
            for (stationIndex in 0 until stationGroups.length()) {
                val station = stationGroups.optJsonObject(stationIndex) ?: continue
                val mac = station.optString("mac")
                val rxRate = station.opt("rx_bitrate")?.toString()?.takeIf { it.isNotBlank() && it != "null" }
                val txRate = station.opt("tx_bitrate")?.toString()?.takeIf { it.isNotBlank() && it != "null" }
                val airtimeRx = station.optLong("airtime_rx_us").takeIf { !station.isNull("airtime_rx_us") }
                val airtimeTx = station.optLong("airtime_tx_us").takeIf { !station.isNull("airtime_tx_us") }
                InfoRow(
                    mac,
                    listOfNotNull(
                        station.optInt("signal").takeIf { !station.isNull("signal") }?.let { "$it dBm" },
                        if (rxRate != null || txRate != null) stringResource(R.string.wifi_station_rx_tx, rxRate ?: "—", txRate ?: "—") else null,
                        if (airtimeRx != null || airtimeTx != null) stringResource(R.string.wifi_station_airtime, airtimeRx?.let(::formatMicroseconds) ?: "—", airtimeTx?.let(::formatMicroseconds) ?: "—") else null,
                    ).joinToString(" · "),
                )
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
            if (capabilities["wifi.radio.configure"] != true && (capabilities["wifi.enable"] == true || capabilities["wifi.disable"] == true)) {
                SwitchSettingRow(
                    title = stringResource(R.string.wifi_state),
                    subtitle = if (enabled) stringResource(R.string.wifi_enabled_state) else stringResource(R.string.wifi_disabled_state),
                    checked = enabled,
                    onCheckedChange = { enabled = it },
                )
                SecondaryActionButton(
                    label = stringResource(R.string.wifi_state_apply),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_enabled", JsonObject().put("enabled", enabled).put("radio", radioId), wifiToggleQueued) },
                    modifier = Modifier.align(Alignment.End),
                )
            }
            if (capabilities["wifi.manage_ssid"] == true && ifaceId != null) {
                HorizontalDivider()
                OutlinedTextField(ssid, { ssid = it }, label = { Text("SSID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                if (networkOptions.isNotEmpty()) OptionSelector(stringResource(R.string.wifi_network_name), newNetwork, networkOptions, { newNetwork = it })
                OptionSelector(stringResource(R.string.wifi_encryption), interfaceEncryption, wifiEncryptionOptions, { interfaceEncryption = it })
                OutlinedTextField(password, { password = it }, label = { Text(stringResource(R.string.new_wifi_password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
                SwitchSettingRow(stringResource(R.string.wifi_state), checked = interfaceEnabled, onCheckedChange = { interfaceEnabled = it })
                SwitchSettingRow(stringResource(R.string.wifi_hidden), checked = interfaceHidden, onCheckedChange = { interfaceHidden = it })
                SwitchSettingRow(stringResource(R.string.wifi_isolation), checked = interfaceIsolated, onCheckedChange = { interfaceIsolated = it })
                SwitchSettingRow(stringResource(R.string.wifi_roaming_r), checked = roamingR, onCheckedChange = { roamingR = it })
                SwitchSettingRow(stringResource(R.string.wifi_roaming_k), checked = roamingK, onCheckedChange = { roamingK = it })
                SwitchSettingRow(stringResource(R.string.wifi_roaming_v), checked = roamingV, onCheckedChange = { roamingV = it })
                if (roamingR) OutlinedTextField(mobilityDomain, { mobilityDomain = it.filter { char -> char.isDigit() || char.lowercaseChar() in 'a'..'f' }.take(4) }, label = { Text(stringResource(R.string.wifi_mobility_domain)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                PrimaryActionButton(
                    label = stringResource(R.string.wifi_save_network),
                    onClick = {
                        val payload = JsonObject()
                            .put("iface", ifaceId)
                            .put("ssid", ssid)
                            .put("network", newNetwork)
                            .put("encryption", interfaceEncryption)
                            .put("enabled", interfaceEnabled)
                            .put("hidden", interfaceHidden)
                            .put("isolate", interfaceIsolated)
                            .put("ieee80211r", roamingR)
                            .put("ieee80211k", roamingK)
                            .put("bss_transition", roamingV)
                        if (password.isNotBlank()) payload.put("key", password)
                        if (roamingR) payload.put("mobility_domain", mobilityDomain.ifBlank { "4f57" })
                        pendingCommand = PendingSafeCommand("wifi.update_ssid", payload, wifiSsidQueued)
                    },
                    modifier = Modifier.align(Alignment.End),
                    enabled = ssid.isNotBlank() && newNetwork.isNotBlank() && (interfaceEncryption == "none" || password.isBlank() || password.length >= 8) && (!roamingR || mobilityDomain.isBlank() || mobilityDomain.length == 4),
                )
            } else if (capabilities["wifi.set_ssid"] == true) {
                HorizontalDivider()
                OutlinedTextField(ssid, { ssid = it }, label = { Text("SSID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                PrimaryActionButton(
                    label = stringResource(R.string.apply_ssid),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_ssid", JsonObject().put("ssid", ssid).put("iface", ifaceId), wifiSsidQueued) },
                    modifier = Modifier.align(Alignment.End),
                    enabled = ssid.isNotBlank(),
                )
            }
            if (capabilities["wifi.manage_ssid"] != true && capabilities["wifi.set_password"] == true) {
                HorizontalDivider()
                OutlinedTextField(password, { password = it }, label = { Text(stringResource(R.string.new_wifi_password)) }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
                PrimaryActionButton(
                    label = stringResource(R.string.change_password),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_password", JsonObject().put("password", password).put("iface", ifaceId), wifiPasswordQueued) },
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
                OptionSelector(stringResource(R.string.wifi_channel), channel, routerChannelOptions, { channel = it })
                PrimaryActionButton(
                    label = stringResource(R.string.change_channel),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_channel", JsonObject().put("channel", channel).put("radio", radioId), wifiChannelQueued) },
                    enabled = channel.isNotBlank(),
                    modifier = Modifier.align(Alignment.End),
                )
            }
            if (capabilities["wifi.set_country"] == true) {
                OptionSelector(stringResource(R.string.wifi_country), country, routerCountryOptions, { country = it })
                PrimaryActionButton(
                    label = stringResource(R.string.change_country),
                    onClick = { pendingCommand = PendingSafeCommand("wifi.set_country", JsonObject().put("country", country).put("radio", radioId), wifiCountryQueued) },
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
                onClick = { pendingCommand = PendingSafeCommand("wifi.set_guest", JsonObject().put("enabled", guestEnabled).put("ssid", guestSsid).put("password", guestPassword).put("radio", radioId), wifiToggleQueued) },
                enabled = !guestEnabled || (guestSsid.isNotBlank() && guestPassword.length >= 8),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }

    if (capabilities.isEmpty()) MessageBanner(stringResource(R.string.capabilities_missing_reinstall))
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
    wifiQr?.let { (networkName, bitmap) ->
        AlertDialog(
            onDismissRequest = { wifiQr = null },
            title = { Text(networkName) },
            text = {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Image(bitmap.asImageBitmap(), contentDescription = stringResource(R.string.wifi_show_qr), modifier = Modifier.fillMaxWidth())
                    Text(stringResource(R.string.wifi_qr_private_hint), style = MaterialTheme.typography.bodySmall)
                }
            },
            confirmButton = { TextButton(onClick = { wifiQr = null }) { Text(stringResource(R.string.close)) } },
        )
    }
}

private fun createWifiQrBitmap(content: String): Bitmap {
    val matrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, 768, 768)
    return Bitmap.createBitmap(768, 768, Bitmap.Config.RGB_565).also { bitmap ->
        for (x in 0 until 768) for (y in 0 until 768) {
            bitmap.setPixel(x, y, if (matrix[x, y]) android.graphics.Color.BLACK else android.graphics.Color.WHITE)
        }
    }
}
enum class NetworkScreenMode {
    Internet,
    Rules,
    Vpn,
}
