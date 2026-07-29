package ru.wrtmonitor.app.api.dto

data class DeviceDto(
    val id: String,
    val name: String,
    val hostname: String,
    val model: String,
    val firmware: String,
    val status: String,
    val lastSeenAt: String?,
)

data class NetworkClientDto(
    val id: String,
    val mac: String,
    val displayName: String?,
    val hostname: String?,
    val vendor: String?,
    val ipAddress: String?,
    val currentIpv4: String?,
    val staticIpv4: String?,
    val ipv6Addresses: List<String>,
    val networkInterface: String?,
    val connectionType: String,
    val connectionName: String?,
    val wifiSsid: String?,
    val wifiBand: String?,
    val signalDbm: Int?,
    val rxBitrate: Long?,
    val txBitrate: Long?,
    val online: Boolean,
    val presenceState: String,
    val presenceSource: String?,
    val lastObservedAt: String?,
    val lastConfirmedAt: String?,
    val isStatic: Boolean,
    val profileId: String?,
    val effectivePolicy: JsonObject,
    val traffic: JsonObject?,
    val firstSeenAt: String?,
    val lastSeenAt: String?,
)

data class ClientProfileDto(
    val id: String,
    val name: String,
    val policy: JsonObject,
)

data class TelemetryDto(
    val createdAt: String?,
    val ageSeconds: Long?,
    val isStale: Boolean,
    val source: String?,
    val dataState: DataStateDto,
    val payload: JsonObject?,
    val agent: AgentStatusDto? = null,
    val wifi: JsonObject? = null,
    val network: JsonObject? = null,
    val clients: JsonObject? = null,
    val system: JsonObject? = null,
    val services: JsonObject? = null,
    val alerts: JsonArray? = null,
)

data class DataStateDto(
    val kind: String,
    val reason: String?,
    val observedAt: String?,
    val ageSeconds: Long?,
)

data class TelemetryHistoryPointDto(
    val createdAt: String,
    val rxBps: Long?,
    val txBps: Long?,
    val rxBytes: Long?,
    val txBytes: Long?,
    val load1m: Double?,
    val memoryPercent: Double?,
    val clientCount: Int?,
)

data class AgentStatusDto(
    val version: String?,
    val status: String?,
    val capabilitiesVersion: Int?,
    val autoUpdateEnabled: Boolean,
    val telemetryIntervalSeconds: Int?,
    val lastUpdateStatus: String?,
    val lastUpdateError: String?,
    val lastUpdateCheck: String?,
    val lastSuccessfulUpdate: String?,
    val availableVersion: String?,
    val rollbackAvailable: Boolean,
    val updateSource: String?,
    val capabilities: Map<String, Boolean>,
    val capabilityReasons: Map<String, String>,
)

data class CommandDto(
    val id: String,
    val commandType: String,
    val status: String,
    val source: String,
    val payload: JsonObject,
    val result: JsonObject?,
    val createdAt: String?,
    val pickedAt: String?,
    val completedAt: String?,
    val expiresAt: String?,
    val lastError: String?,
    val riskLevel: String?,
    val capability: String?,
)

data class ConfigChangeDto(
    val field: String,
    val current: String,
    val proposed: String,
)

data class CommandPreviewDto(
    val transactional: Boolean,
    val configs: List<String>,
    val rollbackTimeoutSeconds: Int,
    val connectivitySensitive: Boolean,
    val changes: List<ConfigChangeDto>,
    val warnings: List<String>,
    val errors: List<String>,
    val canApply: Boolean,
)
