package ru.wrtmonitor.app.viewmodel

import ru.wrtmonitor.app.api.dto.DeviceDto

data class DevicesUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val actionError: String? = null,
    val sessionExpired: Boolean = false,
    val devices: List<DeviceDto> = emptyList(),
)
