package ru.wrtmonitor.app.api.dto

import org.json.JSONObject
import org.json.JSONArray

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
    val effectivePolicy: JSONObject,
    val traffic: JSONObject?,
    val firstSeenAt: String?,
    val lastSeenAt: String?,
)

data class ClientProfileDto(
    val id: String,
    val name: String,
    val policy: JSONObject,
)

data class TelemetryDto(
    val createdAt: String?,
    val ageSeconds: Long?,
    val isStale: Boolean,
    val source: String,
    val payload: JSONObject?,
    val agent: AgentStatusDto? = null,
    val wifi: JSONObject? = null,
    val network: JSONObject? = null,
    val clients: JSONObject? = null,
    val system: JSONObject? = null,
    val services: JSONObject? = null,
    val alerts: JSONArray? = null,
)

data class TelemetryHistoryPointDto(
    val createdAt: String,
    val rxBps: Long,
    val txBps: Long,
    val rxBytes: Long,
    val txBytes: Long,
    val load1m: Double,
    val memoryPercent: Double,
    val clientCount: Int,
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
    val payload: JSONObject,
    val result: JSONObject?,
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
