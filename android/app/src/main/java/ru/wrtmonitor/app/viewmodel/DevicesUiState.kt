package ru.wrtmonitor.app.viewmodel

import ru.wrtmonitor.app.api.dto.DeviceDto

data class DevicesUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val devices: List<DeviceDto> = emptyList(),
)
