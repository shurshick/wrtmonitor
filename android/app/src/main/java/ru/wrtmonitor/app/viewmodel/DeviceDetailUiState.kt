package ru.wrtmonitor.app.viewmodel

import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.EventDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.dto.TelemetryHistoryPointDto

data class DeviceDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val device: DeviceDto? = null,
    val telemetry: TelemetryDto? = null,
    val telemetryHistory: List<TelemetryHistoryPointDto> = emptyList(),
    val telemetryHistoryLoading: Boolean = false,
    val telemetryHistoryError: String? = null,
    val loadedTelemetryRange: String? = null,
    val events: List<EventDto> = emptyList(),
    val quickActionRunning: Boolean = false,
    val quickActionMessage: String? = null,
    val quickActionError: Boolean = false,
    val sessionExpired: Boolean = false,
)
