package ru.wrtmonitor.app.api.dto

data class DeviceEventDto(
    val id: String,
    val type: String,
    val deviceId: String,
    val emittedAt: String,
)
