package ru.wrtmonitor.app.ui.screens

import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.dto.HardwareDto
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.ui.components.InfoRow
import ru.wrtmonitor.app.ui.components.SectionCard
import java.util.Locale

@Composable
internal fun RouterInformationCard(
    hostname: String,
    hardware: HardwareDto?,
    system: JsonObject?,
    connections: String,
) {
    SectionCard(stringResource(R.string.router_information)) {
        InfoRow(stringResource(R.string.hostname), hostname, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.hardware_model), hardware.catalogLabel() ?: hardware?.model, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.soc), hardware.socLabel(), stringResource(R.string.catalog_not_matched))
        InfoRow(stringResource(R.string.processor), hardware.cpuLabel() ?: hardware?.cpu?.observedModel, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.architecture), hardware?.cpu?.architecture ?: hardware?.catalog?.cpuArchitecture, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.cpu_frequency), cpuFrequencyLabel(hardware), stringResource(R.string.unsupported_data))
        InfoRow(stringResource(R.string.kernel), system?.optString("kernel"), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.connections), connections, stringResource(R.string.no_data))
    }
}

@Composable
internal fun HardwareIdentityCard(hardware: HardwareDto?) {
    SectionCard(
        stringResource(R.string.hardware_identity),
        subtitle = stringResource(if (hardware?.catalog?.verified == true) R.string.hardware_profile_verified else R.string.hardware_profile_observed),
    ) {
        InfoRow(stringResource(R.string.hardware_model), hardware?.model, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.hardware_board), hardware?.boardName, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.hardware_target), hardware?.target, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.soc), hardware.socLabel(), stringResource(R.string.catalog_not_matched))
        InfoRow(stringResource(R.string.processor), hardware.cpuLabel() ?: hardware?.cpu?.observedModel, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.architecture), hardware?.cpu?.architecture ?: hardware?.catalog?.cpuArchitecture, stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.cpu_cores), hardware?.cpu?.cores?.toString() ?: hardware?.catalog?.cpuCores?.toString(), stringResource(R.string.no_data))
        InfoRow(stringResource(R.string.cpu_frequency), cpuFrequencyLabel(hardware), stringResource(R.string.unsupported_data))
        InfoRow(stringResource(R.string.thermal_health), thermalStateLabel(hardware?.thermalHealth), stringResource(R.string.unsupported_data))
        InfoRow(
            stringResource(R.string.throttling),
            hardware?.throttling?.takeIf { it.state == "observed" }?.let {
                stringResource(if (it.active == true) R.string.throttling_active else R.string.throttling_inactive)
            },
            stringResource(R.string.unsupported_data),
        )
    }
}

@Composable
internal fun TemperatureSensorsCard(hardware: HardwareDto?, detailed: Boolean) {
    val sensors = hardware?.sensors.orEmpty()
    SectionCard(
        stringResource(R.string.temperature_sensors),
        subtitle = stringResource(R.string.temperature_sensors_count, sensors.size),
    ) {
        if (sensors.isEmpty()) {
            Text(stringResource(R.string.temperature_unsupported))
        } else {
            sensors.forEachIndexed { index, sensor ->
                val current = sensor.currentMilliCelsius?.let { "%.1f °C".format(Locale.US, it / 1000.0) }
                val range = if (sensor.minMilliCelsius != null && sensor.maxMilliCelsius != null) {
                    stringResource(R.string.temperature_sensor_range, sensor.minMilliCelsius / 1000.0, sensor.maxMilliCelsius / 1000.0, sensor.sampleCount)
                } else null
                val supporting = if (detailed) {
                    val limits = listOfNotNull(
                        sensor.warningMilliCelsius?.let { stringResource(R.string.threshold_warning, it / 1000.0) },
                        sensor.criticalMilliCelsius?.let { stringResource(R.string.threshold_critical, it / 1000.0) },
                    ).joinToString(" · ").ifBlank { stringResource(R.string.threshold_unknown) }
                    listOfNotNull(thermalStateLabel(sensor.thermalStatus), range, limits).joinToString(" · ")
                } else range
                InfoRow(sensor.label, current, stringResource(R.string.stale_telemetry), supporting = supporting)
                if (index < sensors.lastIndex) HorizontalDivider()
            }
        }
    }
}

@Composable
private fun cpuFrequencyLabel(hardware: HardwareDto?): String? {
    val current = hardware?.cpu?.currentKhz?.takeIf { it > 0 }
    val maximum = hardware?.cpu?.maxKhz?.takeIf { it > 0 }
    return when {
        current != null && maximum != null -> stringResource(R.string.cpu_frequency_current_max, current / 1000, maximum / 1000)
        current != null -> stringResource(R.string.cpu_frequency_current, current / 1000)
        else -> hardware?.catalog?.cpuMaxMhz?.let { stringResource(R.string.cpu_frequency_catalog, it) }
    }
}

@Composable
private fun thermalStateLabel(state: String?): String? = when (state) {
    "normal" -> stringResource(R.string.thermal_state_normal)
    "warning" -> stringResource(R.string.thermal_state_warning)
    "critical" -> stringResource(R.string.thermal_state_critical)
    "stale" -> stringResource(R.string.thermal_state_stale)
    "unknown" -> stringResource(R.string.thermal_state_unknown)
    else -> null
}

private fun HardwareDto?.catalogLabel(): String? =
    listOfNotNull(this?.catalog?.vendor, this?.catalog?.model).joinToString(" ").takeIf(String::isNotBlank)

private fun HardwareDto?.socLabel(): String? =
    listOfNotNull(this?.catalog?.socVendor, this?.catalog?.socModel).joinToString(" ").takeIf(String::isNotBlank)

private fun HardwareDto?.cpuLabel(): String? =
    listOfNotNull(this?.catalog?.cpuVendor, this?.catalog?.cpuModel).joinToString(" ").takeIf(String::isNotBlank)
