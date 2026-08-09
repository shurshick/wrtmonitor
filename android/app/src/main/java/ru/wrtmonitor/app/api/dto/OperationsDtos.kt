package ru.wrtmonitor.app.api.dto

data class EventDto(
    val id: String,
    val deviceId: String?,
    val eventType: String,
    val severity: String,
    val source: String,
    val title: String,
    val message: String,
    val status: String,
    val occurrenceCount: Int,
    val lastOccurredAt: String?,
    val snoozedUntil: String?,
)

data class NotificationRuleDto(
    val id: String,
    val deviceId: String?,
    val name: String,
    val enabled: Boolean,
    val eventTypes: List<String>,
    val severities: List<String>,
    val channelTypes: List<String>,
)

data class AutomationRuleDto(
    val id: String,
    val deviceId: String?,
    val name: String,
    val enabled: Boolean,
    val triggerType: String,
    val actionCommand: String,
    val conditions: JsonObject,
    val actionPayload: JsonObject,
    val cooldownSeconds: Int,
    val maxRunsPerHour: Int,
    val dryRun: Boolean,
    val allowDisruptive: Boolean,
)

data class AutomationTemplateDto(
    val id: String,
    val name: String,
    val triggerType: String,
    val actionCommand: String,
    val actionPayload: JsonObject,
    val cooldownSeconds: Int,
)

data class AutomationRunDto(
    val id: String,
    val status: String,
    val message: String,
    val createdAt: String,
)
