package ru.wrtmonitor.app.api.dto

data class FirmwareImageDto(
    val name: String,
    val label: String,
    val url: String,
    val sha256: String,
    val model: String,
)

data class FirmwareCatalogDto(
    val status: String,
    val error: String,
    val images: List<FirmwareImageDto>,
)
