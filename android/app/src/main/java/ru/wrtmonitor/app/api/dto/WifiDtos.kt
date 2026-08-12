package ru.wrtmonitor.app.api.dto

data class WifiExperienceDto(
    val state: String,
    val reason: String,
    val observedAt: String?,
    val radios: List<WifiRadioDto>,
    val networks: List<WifiNetworkDto>,
    val stations: List<WifiStationDto>,
)

data class WifiRadioDto(
    val id: String,
    val name: String,
    val band: String,
    val channel: String,
    val country: String,
    val htmode: String,
    val txpower: String,
    val configuredEnabled: Boolean,
    val runtimeState: String,
    val runtimeReason: String,
    val runtimeUp: Boolean?,
    val runtimePending: Boolean?,
    val supportedChannels: List<String>,
    val surveyUtilization: Int?,
    val surveyNoise: Int?,
)

data class WifiNetworkDto(
    val id: String,
    val radioId: String,
    val band: String,
    val ssid: String,
    val enabled: Boolean,
    val encryption: String,
    val network: String,
    val role: String,
    val hidden: Boolean,
    val isolate: Boolean,
    val stationCount: Int,
)

data class WifiStationDto(
    val mac: String,
    val interfaceName: String,
    val ssid: String,
    val band: String,
    val signal: Int?,
    val noise: Int?,
    val rxBitrate: String?,
    val txBitrate: String?,
)

data class WifiQrDto(val ssid: String, val security: String, val wifiUri: String)
