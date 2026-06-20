package ru.wrtmonitor.app.viewmodel

import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto

data class DeviceDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val device: DeviceDto? = null,
    val telemetry: TelemetryDto? = null,
)
