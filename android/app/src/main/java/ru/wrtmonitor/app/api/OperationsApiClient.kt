package ru.wrtmonitor.app.api

import org.json.JSONArray
import org.json.JSONObject
import ru.wrtmonitor.app.api.dto.*

internal class OperationsApiClient(private val transport: ApiTransport) {
    fun submitFeedback(
        message: String,
        appVersion: String,
        category: String = "usability",
    ): ApiResult<Unit> = runCatching {
        val body = JSONObject()
            .put("category", category)
            .put("message", message)
            .put("source", "android")
            .put("app_version", appVersion)
            .put("client_context", JSONObject().put("platform", "android").put("screen", "about"))
        val (status, _) = transport.request("/api/v1/operations/feedback", "POST", body)
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getDiagnosticReport(deviceId: String): ApiResult<String> = runCatching {
        val (status, response) = transport.request("/api/v1/operations/diagnostics/report/$deviceId")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).toString(2)
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getEvents(deviceId: String? = null): ApiResult<List<EventDto>> = runCatching {
        val query = deviceId?.let { "?device_id=$it&limit=100" } ?: "?limit=100"
        val (status, response) = transport.request("/api/v1/operations/events$query")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index -> parseEvent(array.getJSONObject(index)) }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun acknowledgeEvent(eventId: String): ApiResult<EventDto> = runCatching {
        val (status, response) = transport.request("/api/v1/operations/events/$eventId/acknowledge", "POST", JSONObject())
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseEvent(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun snoozeEvent(eventId: String, minutes: Int = 60): ApiResult<EventDto> = runCatching {
        val safeMinutes = minutes.coerceIn(5, 10_080)
        val (status, response) = transport.request("/api/v1/operations/events/$eventId/snooze?minutes=$safeMinutes", "POST", JSONObject())
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseEvent(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getNotificationRules(): ApiResult<List<NotificationRuleDto>> = runCatching {
        val (status, response) = transport.request("/api/v1/operations/notification-rules")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                val channels = item.optJSONArray("channels") ?: JSONArray()
                NotificationRuleDto(
                    id = item.optString("id"),
                    deviceId = item.optString("device_id").takeIf { it.isNotBlank() && it != "null" },
                    name = item.optString("name"),
                    enabled = item.optBoolean("enabled"),
                    eventTypes = item.optJSONArray("event_types").toStringList(),
                    severities = item.optJSONArray("severities").toStringList(),
                    channelTypes = (0 until channels.length()).map { channels.optJSONObject(it)?.optString("type", "in_app") ?: "in_app" },
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun createInAppNotificationRule(deviceId: String, name: String): ApiResult<Unit> = runCatching {
        val body = JSONObject()
            .put("name", name)
            .put("device_id", deviceId)
            .put("enabled", true)
            .put("event_types", JSONArray())
            .put("severities", JSONArray().put("warning").put("critical"))
            .put("channels", JSONArray().put(JSONObject().put("type", "in_app")))
            .put("quiet_hours", JSONObject().put("enabled", false))
            .put("notify_recovery", true)
        val (status, _) = transport.request("/api/v1/operations/notification-rules", "POST", body)
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun deleteNotificationRule(ruleId: String): ApiResult<Unit> = runCatching {
        val (status, _) = transport.request("/api/v1/operations/notification-rules/$ruleId", "DELETE")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getAutomationRules(): ApiResult<List<AutomationRuleDto>> = runCatching {
        val (status, response) = transport.request("/api/v1/operations/automation-rules")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index -> parseAutomationRule(array.getJSONObject(index)) }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getAutomationTemplates(): ApiResult<List<AutomationTemplateDto>> = runCatching {
        val (status, response) = transport.request("/api/v1/operations/automation/templates")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                AutomationTemplateDto(
                    id = item.optString("id"),
                    name = item.optString("name"),
                    triggerType = item.optString("trigger_type"),
                    actionCommand = item.optString("action_command"),
                    actionPayload = (item.optJSONObject("action_payload") ?: JSONObject()).toJsonObject(),
                    cooldownSeconds = item.optInt("cooldown_seconds", 300),
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun createAutomationFromTemplate(deviceId: String, template: AutomationTemplateDto): ApiResult<Unit> = runCatching {
        val body = JSONObject()
            .put("name", template.name)
            .put("device_id", deviceId)
            .put("enabled", true)
            .put("trigger_type", template.triggerType)
            .put("conditions", JSONObject())
            .put("action_command", template.actionCommand)
            .put("action_payload", template.actionPayload.raw)
            .put("cooldown_seconds", template.cooldownSeconds)
            .put("max_runs_per_hour", 6)
            .put("dry_run", false)
            .put("allow_disruptive", false)
        val (status, _) = transport.request("/api/v1/operations/automation-rules", "POST", body)
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun setAutomationEnabled(rule: AutomationRuleDto, enabled: Boolean): ApiResult<Unit> = runCatching {
        val body = JSONObject()
            .put("name", rule.name)
            .put("device_id", rule.deviceId ?: JSONObject.NULL)
            .put("enabled", enabled)
            .put("trigger_type", rule.triggerType)
            .put("conditions", rule.conditions.raw)
            .put("action_command", rule.actionCommand)
            .put("action_payload", rule.actionPayload.raw)
            .put("cooldown_seconds", rule.cooldownSeconds)
            .put("max_runs_per_hour", rule.maxRunsPerHour)
            .put("dry_run", rule.dryRun)
            .put("allow_disruptive", rule.allowDisruptive)
        val (status, _) = transport.request("/api/v1/operations/automation-rules/${rule.id}", "PUT", body)
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun deleteAutomationRule(ruleId: String): ApiResult<Unit> = runCatching {
        val (status, _) = transport.request("/api/v1/operations/automation-rules/$ruleId", "DELETE")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getAutomationRuns(): ApiResult<List<AutomationRunDto>> = runCatching {
        val (status, response) = transport.request("/api/v1/operations/automation-runs?limit=20")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                AutomationRunDto(item.optString("id"), item.optString("status"), item.optString("message"), item.optString("created_at"))
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)
}
