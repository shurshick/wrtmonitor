package ru.wrtmonitor.app.api.dto

data class ManagementOptionDto(
    val value: String,
    val label: String,
    val metadata: String = "",
)

data class WifiRadioOptionDto(
    val id: String,
    val name: String,
    val band: String,
    val channel: String,
    val country: String,
    val htmode: String,
    val supportedChannels: List<String>,
)

data class ManagementOptionsDto(
    val source: String,
    val interfaces: List<String>,
    val networks: List<String>,
    val bridges: List<String>,
    val firewallZones: List<String>,
    val wifiRadios: List<WifiRadioOptionDto>,
    val netmasks: List<ManagementOptionDto>,
    val timezones: List<ManagementOptionDto>,
    val wifiCountries: List<ManagementOptionDto>,
    val fallbackWifiChannels: List<String>,
)
