package ru.wrtmonitor.app.api.dto

import org.json.JSONObject

data class DeviceDto(
    val id: String,
    val name: String,
    val hostname: String,
    val model: String,
    val firmware: String,
    val status: String,
    val lastSeenAt: String?,
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
)

data class AgentStatusDto(
    val version: String?,
    val status: String?,
    val autoUpdateEnabled: Boolean,
    val lastUpdateStatus: String?,
    val lastUpdateError: String?,
    val lastUpdateCheck: String?,
    val lastSuccessfulUpdate: String?,
    val availableVersion: String?,
    val rollbackAvailable: Boolean,
    val updateSource: String?,
    val capabilities: Map<String, Boolean>,
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
