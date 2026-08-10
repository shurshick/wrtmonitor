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
import ru.wrtmonitor.app.api.dto.FirmwareCatalogDto
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
fun SystemControlScreen(
    serverUrl: String,
    accessToken: String,
    device: DeviceDto,
    onSessionExpired: () -> Unit,
    mode: SystemScreenMode = SystemScreenMode.System,
) {
    val scope = rememberCoroutineScope()
    val repository = remember(serverUrl, accessToken) { RouterRepository(serverUrl, accessToken) }
    var telemetry by remember { mutableStateOf<TelemetryDto?>(null) }
    var managementOptions by remember { mutableStateOf<ManagementOptionsDto?>(null) }
    var firmwareCatalog by remember { mutableStateOf<FirmwareCatalogDto?>(null) }
    var commands by remember { mutableStateOf<List<CommandDto>>(emptyList()) }
    var loading by remember(device.id) { mutableStateOf(true) }
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
        loading = true
        scope.launch {
            when (val result = repository.latestTelemetry(device.id)) {
                is ApiResult.Success -> {
                    telemetry = result.data
                    hostnameValue = result.data.system?.optString("hostname").orEmpty().ifBlank { device.hostname }
                    if (!formInitialized) {
                        val time = result.data.system
                        zoneName = time?.optString("zonename").orEmpty()
                        timezoneValue = time?.optString("timezone").orEmpty()
                        ntpEnabled = time?.optBoolean("ntp_enabled", false) ?: false
                        ntpServers = time?.optJsonArray("ntp_servers")?.let { array ->
                            (0 until array.length()).joinToString(", ") { array.optString(it) }
                        }.orEmpty()
                        cronContent = result.data.payload?.optJsonObject("maintenance")?.optString("cron_content").orEmpty()
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
            if (mode == SystemScreenMode.Management) {
                when (val result = repository.firmwareCatalog(device.id)) {
                    is ApiResult.Success -> {
                        firmwareCatalog = result.data
                        if (firmwareUrl.isBlank()) {
                            result.data.images.firstOrNull()?.let { image ->
                                firmwareUrl = image.url
                                firmwareSha256 = image.sha256
                            }
                        }
                    }
                    is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired()
                }
            }
            when (val result = repository.commands(device.id)) {
                is ApiResult.Success -> commands = result.data
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
    val system = telemetry?.payload?.optJsonObject("system")
    val memory = system?.optJsonObject("memory")
    val storage = telemetry?.payload?.optJsonObject("storage")
    val systemSummary = telemetry?.system
    val maintenance = telemetry?.payload?.optJsonObject("maintenance")
    val services = telemetry?.services
    val hardware = telemetry?.hardware
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
    val tokenRotationQueued = stringResource(R.string.token_rotation_queued)

    fun queueSystem(type: String, payload: JsonObject, success: String) {
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

    val uptimeLabel = formatRouterDuration(system?.optLong("uptime", 0) ?: 0)
    val memoryLabel = memory?.let { "${it.optLong("available_kb") / 1024} / ${it.optLong("total_kb") / 1024} MB" } ?: stringResource(R.string.no_data)
    val storageLabel = storage?.let { "${it.optLong("used_kb") / 1024} / ${it.optLong("total_kb") / 1024} MB" } ?: stringResource(R.string.no_data)
    val connectionLabel = systemSummary?.let { "${it.optLong("conntrack_count")} / ${it.optLong("conntrack_max")}" } ?: stringResource(R.string.no_data)

    RouterPageHeader(
        title = stringResource(if (mode == SystemScreenMode.System) R.string.system else R.string.maintenance_title),
        subtitle = stringResource(if (mode == SystemScreenMode.System) R.string.system_screen_summary else R.string.maintenance_summary),
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
    if (mode == SystemScreenMode.System) {
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
        InfoRow(
            stringResource(R.string.hardware_model),
            listOfNotNull(hardware?.catalog?.vendor, hardware?.catalog?.model).joinToString(" ").takeIf { it.isNotBlank() } ?: hardware?.model,
            stringResource(R.string.no_data),
        )
        InfoRow(
            stringResource(R.string.soc),
            listOfNotNull(hardware?.catalog?.socVendor, hardware?.catalog?.socModel).joinToString(" ").takeIf { it.isNotBlank() },
            stringResource(R.string.catalog_not_matched),
        )
        InfoRow(
            stringResource(R.string.processor),
            listOfNotNull(hardware?.catalog?.cpuVendor, hardware?.catalog?.cpuModel).joinToString(" ").takeIf { it.isNotBlank() } ?: hardware?.cpu?.observedModel,
            stringResource(R.string.no_data),
        )
        InfoRow(
            stringResource(R.string.architecture),
            hardware?.cpu?.architecture ?: hardware?.catalog?.cpuArchitecture,
            stringResource(R.string.no_data),
        )
        InfoRow(
            stringResource(R.string.cpu_frequency),
            hardware?.cpu?.currentKhz?.takeIf { it > 0 }?.let { current ->
                val maximum = hardware.cpu.maxKhz?.takeIf { it > 0 }
                if (maximum != null) {
                    stringResource(R.string.cpu_frequency_current_max, current / 1000, maximum / 1000)
                } else {
                    stringResource(R.string.cpu_frequency_current, current / 1000)
                }
            } ?: hardware?.catalog?.cpuMaxMhz?.let { stringResource(R.string.cpu_frequency_catalog, it) },
            stringResource(R.string.unsupported_data),
        )
        InfoRow(stringResource(R.string.kernel), systemSummary?.optString("kernel"), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.connections), connectionLabel, stringResource(R.string.no_data))
    }
    SectionCard(
        stringResource(R.string.temperature_sensors),
        subtitle = stringResource(R.string.temperature_sensors_count, hardware?.sensors?.size ?: 0),
    ) {
        if (hardware?.sensors.isNullOrEmpty()) {
            Text(stringResource(R.string.temperature_unsupported), style = MaterialTheme.typography.bodyMedium)
        } else {
            hardware?.sensors?.forEachIndexed { index, sensor ->
                val current = sensor.currentMilliCelsius?.let { "%.1f °C".format(Locale.US, it / 1000.0) }
                val range = if (sensor.minMilliCelsius != null && sensor.maxMilliCelsius != null) {
                    stringResource(
                        R.string.temperature_sensor_range,
                        sensor.minMilliCelsius / 1000.0,
                        sensor.maxMilliCelsius / 1000.0,
                        sensor.sampleCount,
                    )
                } else null
                InfoRow(sensor.label, current, stringResource(R.string.stale_telemetry), supporting = range)
                if (index < hardware.sensors.lastIndex) HorizontalDivider()
            }
        }
    }
    }
    if (mode == SystemScreenMode.System && services != null) {
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
    if (mode == SystemScreenMode.System && capabilities["system.set_hostname"] == true) {
        ExpandableSettingsCard(stringResource(R.string.device_name), hostnameValue) {
            OutlinedTextField(hostnameValue, { hostnameValue = it }, label = { Text(stringResource(R.string.new_hostname)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(
                label = stringResource(R.string.change_hostname),
                onClick = { pendingSystemCommand = PendingSafeCommand("system.set_hostname", JsonObject().put("hostname", hostnameValue), hostnameQueued) },
                enabled = hostnameValue.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
    if (mode == SystemScreenMode.System && (capabilities["system.set_timezone"] == true || capabilities["system.set_ntp"] == true)) {
        ExpandableSettingsCard(stringResource(R.string.time_settings), zoneName) {
            if (capabilities["system.set_timezone"] == true) {
                OptionSelector(
                    stringResource(R.string.timezone_region),
                    zoneName,
                    managementOptions?.timezones.orEmpty().map { SelectOption(it.value, it.label) },
                    {
                        zoneName = it
                        timezoneValue = managementOptions?.timezones?.firstOrNull { option -> option.value == it }?.metadata.orEmpty()
                    },
                )
                PrimaryActionButton(
                    label = stringResource(R.string.save_time_settings),
                    onClick = { pendingSystemCommand = PendingSafeCommand("system.set_timezone", JsonObject().put("zonename", zoneName).put("timezone", timezoneValue), systemCommandQueued) },
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
                    onClick = { pendingSystemCommand = PendingSafeCommand("system.set_ntp", JsonObject().put("enabled", ntpEnabled).put("servers", ntpServers), systemCommandQueued) },
                    enabled = !ntpEnabled || ntpServers.isNotBlank(),
                    modifier = Modifier.align(Alignment.End),
                )
            }
        }
    }
    if (mode == SystemScreenMode.System && capabilities["system.restart_service"] == true) {
        ExpandableSettingsCard(stringResource(R.string.service_management), stringResource(R.string.service_management_summary)) {
            listOf("dnsmasq", "firewall", "odhcpd", "network").forEach { service ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(service, modifier = Modifier.weight(1f))
                    TextButton(onClick = { pendingSystemCommand = PendingSafeCommand("system.restart_service", JsonObject().put("service", service), serviceQueued) }) {
                        Text(stringResource(R.string.restart_service))
                    }
                }
            }
        }
    }
    if (mode == SystemScreenMode.Management && capabilities["maintenance.modules.write"] == true) {
        val moduleItems = telemetry?.payload?.optJsonObject("modules")?.optJsonArray("items")
        if (moduleItems != null && moduleItems.length() > 0) {
            ExpandableSettingsCard(stringResource(R.string.openwrt_modules), stringResource(R.string.openwrt_modules_summary)) {
                (0 until moduleItems.length()).mapNotNull(moduleItems::optJsonObject)
                    .filter { it.optBoolean("supported") }
                    .forEach { item ->
                        val moduleId = item.optString("id")
                        val installed = item.optBoolean("installed")
                        val running = item.optBoolean("running")
                        val hardwareCount = item.optInt("hardware_count")
                        val label = when (moduleId) {
                            "storage" -> stringResource(R.string.module_storage)
                            "smb" -> stringResource(R.string.module_smb)
                            "nfs" -> stringResource(R.string.module_nfs)
                            "ftp" -> stringResource(R.string.module_ftp)
                            "dlna" -> stringResource(R.string.module_dlna)
                            "printer" -> stringResource(R.string.module_printer)
                            "modem" -> stringResource(R.string.module_modem)
                            else -> moduleId
                        }
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(label, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text(
                                    buildString {
                                        append(if (installed) stringResource(R.string.module_installed) else stringResource(R.string.module_not_installed))
                                        if (running) append(" · ${stringResource(R.string.service_running)}")
                                        if (hardwareCount > 0) append(" · ${stringResource(R.string.module_devices, hardwareCount)}")
                                    },
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                            if (!installed) {
                                TextButton(onClick = { pendingSystemCommand = PendingSafeCommand("maintenance.module.configure", JsonObject().put("module", moduleId).put("action", "install"), systemCommandQueued) }) {
                                    Text(stringResource(R.string.install_package))
                                }
                            } else {
                                Column(horizontalAlignment = Alignment.End) {
                                    if (moduleId !in setOf("storage", "modem")) {
                                        TextButton(onClick = { pendingSystemCommand = PendingSafeCommand("maintenance.module.configure", JsonObject().put("module", moduleId).put("action", if (running) "disable" else "enable"), systemCommandQueued) }) {
                                            Text(stringResource(if (running) R.string.stop_service else R.string.start_service))
                                        }
                                    }
                                    TextButton(onClick = { pendingSystemCommand = PendingSafeCommand("maintenance.module.configure", JsonObject().put("module", moduleId).put("action", "remove"), systemCommandQueued) }) {
                                        Text(stringResource(R.string.remove_package))
                                    }
                                }
                            }
                        }
                        HorizontalDivider()
                    }
            }
        }
    }
    if (mode == SystemScreenMode.Management && (capabilities["maintenance.packages.read"] == true || capabilities["maintenance.packages.write"] == true)) {
        ExpandableSettingsCard(stringResource(R.string.router_packages), stringResource(R.string.router_packages_summary)) {
            if (capabilities["maintenance.packages.read"] == true) {
                TonalActionButton(stringResource(R.string.refresh_package_catalog), { pendingSystemCommand = PendingSafeCommand("maintenance.packages.refresh", JsonObject(), systemCommandQueued) })
            }
            if (capabilities["maintenance.packages.write"] == true) {
                OutlinedTextField(packageName, { packageName = it }, label = { Text(stringResource(R.string.package_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                ActionRow {
                    PrimaryActionButton(stringResource(R.string.install_package), { pendingSystemCommand = PendingSafeCommand("maintenance.package.install", JsonObject().put("package", packageName), systemCommandQueued) }, enabled = packageName.isNotBlank())
                    TextButton({ pendingSystemCommand = PendingSafeCommand("maintenance.package.remove", JsonObject().put("package", packageName), systemCommandQueued) }, enabled = packageName.isNotBlank()) { Text(stringResource(R.string.remove_package)) }
                }
            }
            maintenance?.optJsonObject("packages")?.optJsonArray("upgradable_items")?.let { items ->
                if (items.length() > 0) {
                    HorizontalDivider()
                    Text(stringResource(R.string.package_updates_available, items.length()), style = MaterialTheme.typography.titleSmall)
                    (0 until items.length()).mapNotNull(items::optJsonObject).forEach { item ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(item.optString("name"), maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text("${item.optString("current_version")} → ${item.optString("available_version")}", style = MaterialTheme.typography.bodySmall)
                            }
                            TextButton(onClick = { pendingSystemCommand = PendingSafeCommand("maintenance.package.upgrade", JsonObject().put("package", item.optString("name")), systemCommandQueued) }) {
                                Text(stringResource(R.string.update_package))
                            }
                        }
                    }
                }
            }
        }
    }
    if (mode == SystemScreenMode.Management && capabilities["maintenance.backup"] == true) {
        ExpandableSettingsCard(stringResource(R.string.configuration_backup), stringResource(R.string.configuration_backup_summary)) {
            TonalActionButton(stringResource(R.string.create_backup), { pendingSystemCommand = PendingSafeCommand("maintenance.backup.create", JsonObject(), systemCommandQueued) })
            OutlinedTextField(backupArchive, { backupArchive = it }, label = { Text(stringResource(R.string.backup_base64)) }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            SecondaryActionButton(stringResource(R.string.restore_backup), { pendingSystemCommand = PendingSafeCommand("maintenance.backup.restore", JsonObject().put("archive_base64", backupArchive), systemCommandQueued) }, enabled = backupArchive.isNotBlank())
        }
    }
    if (mode == SystemScreenMode.Management && capabilities["maintenance.sysupgrade.check"] == true) {
        ExpandableSettingsCard(stringResource(R.string.openwrt_update), stringResource(R.string.openwrt_update_summary)) {
            val firmwareOptions = firmwareCatalog?.images.orEmpty().map { SelectOption(it.url, it.label) }
            if (firmwareOptions.isNotEmpty()) {
                OptionSelector(stringResource(R.string.official_firmware), firmwareUrl, firmwareOptions, { selected ->
                    firmwareUrl = selected
                    firmwareSha256 = firmwareCatalog?.images?.firstOrNull { it.url == selected }?.sha256.orEmpty()
                })
            } else {
                Text(firmwareCatalog?.error.orEmpty().ifBlank { stringResource(R.string.firmware_catalog_unavailable) }, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(firmwareUrl, { firmwareUrl = it }, label = { Text(stringResource(R.string.firmware_url)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(firmwareSha256, { firmwareSha256 = it }, label = { Text("SHA-256") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            }
            PrimaryActionButton(stringResource(R.string.validate_firmware), { pendingSystemCommand = PendingSafeCommand("maintenance.sysupgrade.check", JsonObject().put("url", firmwareUrl).put("sha256", firmwareSha256).put("expected_model", firmwareCatalog?.images?.firstOrNull { it.url == firmwareUrl }?.model.orEmpty()).put("preserve_config", true), systemCommandQueued) }, enabled = firmwareUrl.startsWith("https://") && firmwareSha256.length == 64)
            if (capabilities["maintenance.sysupgrade.apply"] == true) {
                SecondaryActionButton(stringResource(R.string.install_validated_firmware), { pendingSystemCommand = PendingSafeCommand("maintenance.sysupgrade.apply", JsonObject().put("sha256", firmwareSha256).put("preserve_config", true), systemCommandQueued) }, enabled = firmwareSha256.length == 64)
            }
        }
    }
    if (mode == SystemScreenMode.Management && (capabilities["maintenance.logs"] == true || capabilities["maintenance.processes"] == true || capabilities["maintenance.cron"] == true)) {
        ExpandableSettingsCard(stringResource(R.string.advanced_maintenance), stringResource(R.string.advanced_maintenance_summary)) {
            if (capabilities["maintenance.logs"] == true) {
                OutlinedTextField(logLines, { logLines = it.filter(Char::isDigit) }, label = { Text(stringResource(R.string.log_lines)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                TonalActionButton(stringResource(R.string.request_logs), { pendingSystemCommand = PendingSafeCommand("maintenance.logs.read", JsonObject().put("lines", logLines.toIntOrNull() ?: 100), systemCommandQueued) })
            }
            if (capabilities["maintenance.processes"] == true) {
                maintenance?.optString("process_snapshot")?.takeIf(String::isNotBlank)?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 12, overflow = TextOverflow.Ellipsis)
                }
                TonalActionButton(stringResource(R.string.refresh_processes), { pendingSystemCommand = PendingSafeCommand("maintenance.processes.read", JsonObject(), systemCommandQueued) })
                OutlinedTextField(processPid, { processPid = it.filter(Char::isDigit) }, label = { Text("PID") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                OptionSelector("Signal", processSignal, processSignalOptions, { processSignal = it })
                SecondaryActionButton(stringResource(R.string.terminate_process), { pendingSystemCommand = PendingSafeCommand("maintenance.process.signal", JsonObject().put("pid", processPid.toIntOrNull() ?: 0).put("signal", processSignal), systemCommandQueued) }, enabled = (processPid.toIntOrNull() ?: 0) > 1)
            }
            if (capabilities["maintenance.cron"] == true) {
                TonalActionButton(stringResource(R.string.reload_schedule), { pendingSystemCommand = PendingSafeCommand("maintenance.cron.read", JsonObject(), systemCommandQueued) })
                OutlinedTextField(cronContent, { cronContent = it }, label = { Text(stringResource(R.string.root_crontab)) }, modifier = Modifier.fillMaxWidth(), minLines = 3)
                SecondaryActionButton(stringResource(R.string.save_schedule), { pendingSystemCommand = PendingSafeCommand("maintenance.cron.set", JsonObject().put("content", cronContent), systemCommandQueued) })
            }
        }
    }
    if (mode == SystemScreenMode.Management && capabilities["system.restart_service"] == true) {
        val serviceItems = maintenance?.optJsonArray("services")
        ExpandableSettingsCard(stringResource(R.string.service_management), stringResource(R.string.service_management_summary)) {
            TonalActionButton(stringResource(R.string.refresh_services), { pendingSystemCommand = PendingSafeCommand("maintenance.services.read", JsonObject(), systemCommandQueued) })
            if (serviceItems == null || serviceItems.length() == 0) {
                Text(stringResource(R.string.empty_services), color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                (0 until serviceItems.length()).mapNotNull(serviceItems::optJsonObject).forEach { item ->
                    val serviceName = item.optString("name")
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(serviceName, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(if (item.optBoolean("running")) stringResource(R.string.service_running) else stringResource(R.string.service_stopped), style = MaterialTheme.typography.bodySmall)
                        }
                        TextButton(onClick = { pendingSystemCommand = PendingSafeCommand("maintenance.service.set", JsonObject().put("service", serviceName).put("action", "restart"), serviceQueued) }) {
                            Text(stringResource(R.string.restart_service))
                        }
                    }
                }
            }
        }
    }
    if (mode == SystemScreenMode.Management && (capabilities["maintenance.diagnostics.bundle"] == true || capabilities["maintenance.recovery"] == true)) {
        ExpandableSettingsCard(stringResource(R.string.recovery_tools), stringResource(R.string.recovery_tools_summary)) {
            if (capabilities["maintenance.diagnostics.bundle"] == true) TonalActionButton(stringResource(R.string.create_diagnostic_bundle), { pendingSystemCommand = PendingSafeCommand("maintenance.diagnostics.bundle", JsonObject(), systemCommandQueued) })
            if (capabilities["maintenance.recovery"] == true) ActionRow {
                SecondaryActionButton(stringResource(R.string.enable_recovery_mode), { pendingSystemCommand = PendingSafeCommand("maintenance.recovery.enable", JsonObject(), systemCommandQueued) })
                TextButton({ pendingSystemCommand = PendingSafeCommand("maintenance.recovery.disable", JsonObject(), systemCommandQueued) }) { Text(stringResource(R.string.disable_recovery_mode)) }
            }
        }
    }
    if (
        mode == SystemScreenMode.Management && capabilities["diagnostics.check_server"] == true ||
        mode == SystemScreenMode.System && capabilities["system.reboot"] == true
    ) SectionCard(stringResource(R.string.system_actions), subtitle = stringResource(R.string.system_actions_summary)) {
        ActionRow {
            if (mode == SystemScreenMode.Management && capabilities["diagnostics.check_server"] == true) {
                TonalActionButton(
                    label = stringResource(R.string.diagnostics),
                    onClick = {
                        scope.launch {
                            when (val result = repository.createCommand(
                                device.id,
                                "diagnostics.run",
                                JsonObject(),
                                confirmed = true,
                            )) {
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
            if (mode == SystemScreenMode.System && capabilities["system.reboot"] == true) {
                SecondaryActionButton(stringResource(R.string.reboot), { confirmReboot = true })
            }
        }
        latestDiagnostics?.let {
            InfoRow(stringResource(R.string.last_diagnostics), it.status, stringResource(R.string.no_data))
        }
    }
    MessageBanner(message, error = messageIsError)
    if (mode == SystemScreenMode.Management) AgentSection(
        agent = telemetry?.agent,
        actionError = "",
        onCheckUpdate = { queueSystem("agent.update", JsonObject(), updateCheckQueued) },
        onSetInterval = { seconds ->
            queueSystem("agent.set_interval", JsonObject().put("interval_seconds", seconds), intervalChangeQueued)
        },
        onEnableAutoUpdate = {
            queueSystem("agent.set_auto_update", JsonObject().put("enabled", true), autoUpdateEnableQueued)
        },
        onDisableAutoUpdate = {
            queueSystem("agent.set_auto_update", JsonObject().put("enabled", false), autoUpdateDisableQueued)
        },
        onRollback = { confirmAgentRollback = true },
        onRotateToken = {
            pendingSystemCommand = PendingSafeCommand("agent.rotate_token", JsonObject(), tokenRotationQueued)
        },
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
                        when (val result = repository.createCommand(
                            device.id,
                            "router.reboot",
                            JsonObject(),
                            confirmed = true,
                        )) {
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
                queueSystem("agent.rollback", JsonObject(), rollbackQueued)
            }) { Text(stringResource(R.string.rollback_action)) }
        },
        dismissButton = { TextButton(onClick = { confirmAgentRollback = false }) { Text(stringResource(R.string.cancel)) } },
    )
    pendingSystemCommand?.let { command -> SafeCommandDialog(
        repository, device.id, command,
        onDismiss = { pendingSystemCommand = null },
        onApply = {
            pendingSystemCommand = null
            queueSystem(command.type, command.payload, command.successMessage)
        },
        onSessionExpired = onSessionExpired,
    ) }
}
