package ru.wrtmonitor.app.api.dto

import org.json.JSONObject

data class DeviceDto(val id: String, val name: String, val hostname: String, val model: String, val firmware: String, val status: String, val lastSeenAt: String?)
data class TelemetryDto(val createdAt: String?, val ageSeconds: Long?, val isStale: Boolean, val source: String, val payload: JSONObject?)
