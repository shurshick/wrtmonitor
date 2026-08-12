package ru.wrtmonitor.app.api

import org.json.JSONArray
import org.json.JSONObject
import ru.wrtmonitor.app.api.dto.AgentStatusDto
import ru.wrtmonitor.app.api.dto.AutomationRuleDto
import ru.wrtmonitor.app.api.dto.AutomationRunDto
import ru.wrtmonitor.app.api.dto.AutomationTemplateDto
import ru.wrtmonitor.app.api.dto.CommandDto
import ru.wrtmonitor.app.api.dto.CommandPreviewDto
import ru.wrtmonitor.app.api.dto.ClientProfileDto
import ru.wrtmonitor.app.api.dto.ClientActivityDto
import ru.wrtmonitor.app.api.dto.ClientConfigureResultDto
import ru.wrtmonitor.app.api.dto.ClientPolicyApplicationDto
import ru.wrtmonitor.app.api.dto.ClientTrafficPointDto
import ru.wrtmonitor.app.api.dto.ConfigChangeDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.EventDto
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.api.dto.ManagementOptionDto
import ru.wrtmonitor.app.api.dto.ManagementOptionsDto
import ru.wrtmonitor.app.api.dto.ClientPolicyPresetDto
import ru.wrtmonitor.app.api.dto.FirmwareCatalogDto
import ru.wrtmonitor.app.api.dto.FirmwareImageDto
import ru.wrtmonitor.app.api.dto.WifiRadioOptionDto
import ru.wrtmonitor.app.api.dto.DataStateDto
import ru.wrtmonitor.app.api.dto.NetworkClientDto
import ru.wrtmonitor.app.api.dto.NotificationRuleDto
import ru.wrtmonitor.app.api.dto.HardwareCatalogDto
import ru.wrtmonitor.app.api.dto.HardwareCpuDto
import ru.wrtmonitor.app.api.dto.HardwareDto
import ru.wrtmonitor.app.api.dto.HardwareSensorDto
import ru.wrtmonitor.app.api.dto.HardwareThrottlingDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.dto.TelemetryHistoryPointDto
import ru.wrtmonitor.app.api.dto.HealthDto
import ru.wrtmonitor.app.api.dto.HealthItemDto
import ru.wrtmonitor.app.api.dto.toJsonArray
import ru.wrtmonitor.app.api.dto.toJsonObject
import java.util.UUID

class WrtMonitorApi(private val serverUrl: String, private val accessToken: String = "") {
    private class ApiHttpException(
        val statusCode: Int,
        message: String,
        val code: String? = null,
    ) : IllegalStateException(message)

    private fun request(path: String, method: String = "GET", body: JSONObject? = null): Pair<Int, String> {
        val headers = if (accessToken.isBlank()) emptyMap() else mapOf(
            "Authorization" to "Bearer $accessToken",
        )
        return SharedHttpClient.request(
            "${serverUrl.trim().trimEnd('/')}$path",
            method,
            body,
            headers,
        )
    }

    data class AuthTokens(val accessToken: String, val refreshToken: String)

    data class PairingResult(
        val tokens: AuthTokens,
        val serverUrl: String,
        val ownerName: String,
    )

    data class UserSessionDto(
        val id: String,
        val clientName: String,
        val clientType: String,
        val ipAddress: String,
        val createdAt: String,
        val lastUsedAt: String,
        val expiresAt: String,
        val revoked: Boolean,
    )

    data class OperationNotificationDto(
        val severity: String,
        val title: String,
        val message: String,
    )

    fun login(username: String, password: String): ApiResult<AuthTokens> = runCatching {
        val (status, response) = request(
            "/api/v1/auth/login",
            "POST",
            JSONObject().put("username", username).put("password", password),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseAuthTokens(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun exchangeMobilePairing(pairingToken: String, clientName: String): ApiResult<PairingResult> = runCatching {
        val (status, response) = request(
            "/api/v1/mobile-pairing/exchange",
            "POST",
            JSONObject()
                .put("pairing_token", pairingToken)
                .put("client_name", clientName),
        )
        if (status !in 200..299) {
            val code = runCatching {
                JSONObject(response).optJSONObject("detail")?.optString("code")
            }.getOrNull()
            throw ApiHttpException(status, pairingErrorMessage(code, status), code)
        }
        val json = JSONObject(response)
        PairingResult(
            tokens = parseAuthTokens(json),
            serverUrl = json.getString("server_url").trimEnd('/'),
            ownerName = json.optJSONObject("owner")?.optString("username").orEmpty(),
        )
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun refresh(refreshToken: String): ApiResult<AuthTokens> = runCatching {
        val (status, response) = request(
            "/api/v1/auth/refresh",
            "POST",
            JSONObject().put("refresh_token", refreshToken),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseAuthTokens(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun logout(refreshToken: String): ApiResult<Unit> = runCatching {
        val (status, _) = request(
            "/api/v1/auth/logout",
            "POST",
            JSONObject().put("refresh_token", refreshToken),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getSessions(): ApiResult<List<UserSessionDto>> = runCatching {
        val (status, response) = request("/api/v1/auth/sessions?active_only=true")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                UserSessionDto(
                    id = item.optString("id"),
                    clientName = item.optString("client_name", "Unknown client"),
                    clientType = item.optString("client_type", "password"),
                    ipAddress = item.optString("ip_address"),
                    createdAt = item.optString("created_at"),
                    lastUsedAt = item.optString("last_used_at"),
                    expiresAt = item.optString("expires_at"),
                    revoked = !item.isNull("revoked_at"),
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun revokeSession(sessionId: String): ApiResult<Unit> = runCatching {
        val (status, _) = request("/api/v1/auth/sessions/$sessionId", "DELETE")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun changePassword(currentPassword: String, newPassword: String): ApiResult<Unit> = runCatching {
        val (status, _) = request(
            "/api/v1/auth/change-password",
            "POST",
            JSONObject()
                .put("current_password", currentPassword)
                .put("new_password", newPassword)
                .put("new_password_confirm", newPassword),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getOperationNotifications(): ApiResult<List<OperationNotificationDto>> = runCatching {
        val (status, response) = request("/api/v1/operations/notifications")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                OperationNotificationDto(
                    severity = item.optString("severity"),
                    title = item.optString("title"),
                    message = item.optString("message"),
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    private fun parseAuthTokens(json: JSONObject) = AuthTokens(
        accessToken = json.getString("access_token"),
        refreshToken = json.getString("refresh_token"),
    )

    fun getDevices(): ApiResult<List<DeviceDto>> = runCatching {
        val (status, response) = request("/api/v1/devices")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                DeviceDto(
                    id = item.optString("id"),
                    name = item.optString("name"),
                    hostname = item.optString("hostname"),
                    model = item.optString("model"),
                    firmware = item.optString("firmware"),
                    status = item.optString("status"),
                    lastSeenAt = item.optString("last_seen_at").takeIf { value -> value.isNotBlank() && value != "null" },
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getLatestTelemetry(deviceId: String): ApiResult<TelemetryDto> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/telemetry/latest")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).let { json ->
            TelemetryDto(
                createdAt = json.optString("created_at").takeIf { it.isNotBlank() && it != "null" },
                ageSeconds = if (json.isNull("age_seconds")) null else json.optLong("age_seconds"),
                isStale = json.optBoolean("is_stale"),
                source = json.optString("source").takeIf { it.isNotBlank() && it != "null" },
                dataState = json.optJSONObject("data_state").let { state ->
                    DataStateDto(
                        kind = state?.optString("kind", "error") ?: "error",
                        reason = state?.optString("reason")?.takeIf { it.isNotBlank() && it != "null" },
                        observedAt = state?.optString("observed_at")?.takeIf { it.isNotBlank() && it != "null" },
                        ageSeconds = state?.takeUnless { it.isNull("age_seconds") }?.optLong("age_seconds"),
                    )
                },
                payload = json.optJSONObject("telemetry")?.toJsonObject(),
                agent = json.optJSONObject("agent")?.let(::parseAgentStatus),
                wifi = json.optJSONObject("wifi")?.toJsonObject(),
                network = json.optJSONObject("network")?.toJsonObject(),
                clients = json.optJSONObject("clients")?.toJsonObject(),
                system = json.optJSONObject("system")?.toJsonObject(),
                services = json.optJSONObject("services")?.toJsonObject(),
                hardware = json.optJSONObject("hardware")?.let(::parseHardware),
                health = json.optJSONObject("health")?.let(::parseHealth),
                alerts = json.optJSONArray("alerts")?.toJsonArray(),
            )
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getTelemetryHistory(deviceId: String, limit: Int = 120, range: String = "live"): ApiResult<List<TelemetryHistoryPointDto>> = runCatching {
        val safeLimit = limit.coerceIn(2, 120)
        val safeRange = range.takeIf { it in setOf("live", "24h", "7d", "30d") } ?: "live"
        val (status, response) = request("/api/v1/devices/$deviceId/telemetry/history?limit=$safeLimit&range=$safeRange")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val points = JSONObject(response).optJSONArray("points") ?: JSONArray()
        (0 until points.length()).map { index ->
            points.getJSONObject(index).let { point ->
                TelemetryHistoryPointDto(
                    createdAt = point.optString("created_at"),
                    rxBps = point.optLong("rx_bps").takeIf { !point.isNull("rx_bps") },
                    txBps = point.optLong("tx_bps").takeIf { !point.isNull("tx_bps") },
                    rxBytes = point.optLong("rx_bytes").takeIf { !point.isNull("rx_bytes") },
                    txBytes = point.optLong("tx_bytes").takeIf { !point.isNull("tx_bytes") },
                    load1m = point.optDouble("load_1m").takeIf { !point.isNull("load_1m") },
                    memoryPercent = point.optDouble("memory_percent").takeIf { !point.isNull("memory_percent") },
                    temperatureCelsius = point.optDouble("temperature_celsius").takeIf { !point.isNull("temperature_celsius") },
                    storagePercent = point.optDouble("storage_percent").takeIf { !point.isNull("storage_percent") },
                    clientCount = point.optInt("client_count").takeIf { !point.isNull("client_count") },
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getNetworkClients(deviceId: String): ApiResult<List<NetworkClientDto>> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/clients")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            parseNetworkClient(array.getJSONObject(index))
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getNetworkClient(deviceId: String, clientId: String): ApiResult<NetworkClientDto> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/clients/$clientId")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseNetworkClient(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getClientTraffic(deviceId: String, clientId: String): ApiResult<List<ClientTrafficPointDto>> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/clients/$clientId/traffic?limit=96")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                ClientTrafficPointDto(
                    rxBytes = item.optLong("rx_bytes"),
                    txBytes = item.optLong("tx_bytes"),
                    rxDelta = item.optLong("rx_delta"),
                    txDelta = item.optLong("tx_delta"),
                    createdAt = item.optString("created_at"),
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getClientActivity(deviceId: String, clientId: String): ApiResult<List<ClientActivityDto>> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/clients/$clientId/activity?limit=50")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                ClientActivityDto(
                    state = item.optString("state", "offline"),
                    source = item.optString("source").takeIf { it.isNotBlank() && it != "null" },
                    ipAddress = item.optString("ip_address").takeIf { it.isNotBlank() && it != "null" },
                    networkInterface = item.optString("interface").takeIf { it.isNotBlank() && it != "null" },
                    occurredAt = item.optString("occurred_at"),
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getClientProfiles(deviceId: String): ApiResult<List<ClientProfileDto>> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/client-profiles")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                ClientProfileDto(item.optString("id"), item.optString("name"), (item.optJSONObject("policy") ?: JSONObject()).toJsonObject())
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun createClientProfile(deviceId: String, name: String, blocked: Boolean): ApiResult<Unit> = runCatching {
        val policy = JSONObject()
            .put("blocked", blocked)
            .put("schedule", JSONObject().put("enabled", false).put("weekdays", JSONArray()).put("start", "").put("stop", ""))
            .put("qos", JSONObject().put("priority", "normal").put("download_kbps", 0).put("upload_kbps", 0))
        val (status, _) = request(
            "/api/v1/devices/$deviceId/client-profiles",
            "POST",
            JSONObject().put("name", name).put("policy", policy),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun deleteClientProfile(deviceId: String, profileId: String): ApiResult<Unit> = runCatching {
        val (status, _) = request("/api/v1/devices/$deviceId/client-profiles/$profileId", "DELETE")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun configureNetworkClient(
        deviceId: String,
        clientId: String,
        displayName: String,
        deviceType: String,
        profileId: String?,
        policy: JsonObject,
    ): ApiResult<ClientConfigureResultDto> = runCatching {
        val (status, response) = request(
            "/api/v1/devices/$deviceId/clients/$clientId/configure",
            "POST",
            JSONObject()
                .put("display_name", displayName)
                .put("device_type", deviceType)
                .put("profile_id", profileId ?: JSONObject.NULL)
                .put("policy", policy.raw),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val result = JSONObject(response)
        ClientConfigureResultDto(
            client = parseNetworkClient(result.getJSONObject("client")),
            commandId = result.optString("command_id"),
            status = result.optString("status", "queued"),
        )
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun deleteNetworkClient(deviceId: String, clientId: String): ApiResult<Unit> = runCatching {
        val (status, _) = request("/api/v1/devices/$deviceId/clients/$clientId", "DELETE")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getDeviceAgent(deviceId: String): ApiResult<AgentStatusDto> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/agent")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseAgentStatus(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getEvents(deviceId: String? = null): ApiResult<List<EventDto>> = runCatching {
        val query = deviceId?.let { "?device_id=$it&limit=100" } ?: "?limit=100"
        val (status, response) = request("/api/v1/operations/events$query")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index -> parseEvent(array.getJSONObject(index)) }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun acknowledgeEvent(eventId: String): ApiResult<EventDto> = runCatching {
        val (status, response) = request("/api/v1/operations/events/$eventId/acknowledge", "POST", JSONObject())
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseEvent(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun snoozeEvent(eventId: String, minutes: Int = 60): ApiResult<EventDto> = runCatching {
        val safeMinutes = minutes.coerceIn(5, 10_080)
        val (status, response) = request("/api/v1/operations/events/$eventId/snooze?minutes=$safeMinutes", "POST", JSONObject())
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseEvent(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getNotificationRules(): ApiResult<List<NotificationRuleDto>> = runCatching {
        val (status, response) = request("/api/v1/operations/notification-rules")
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
        val (status, _) = request("/api/v1/operations/notification-rules", "POST", body)
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun deleteNotificationRule(ruleId: String): ApiResult<Unit> = runCatching {
        val (status, _) = request("/api/v1/operations/notification-rules/$ruleId", "DELETE")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getAutomationRules(): ApiResult<List<AutomationRuleDto>> = runCatching {
        val (status, response) = request("/api/v1/operations/automation-rules")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index -> parseAutomationRule(array.getJSONObject(index)) }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getAutomationTemplates(): ApiResult<List<AutomationTemplateDto>> = runCatching {
        val (status, response) = request("/api/v1/operations/automation/templates")
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
        val (status, _) = request("/api/v1/operations/automation-rules", "POST", body)
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
        val (status, _) = request("/api/v1/operations/automation-rules/${rule.id}", "PUT", body)
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun deleteAutomationRule(ruleId: String): ApiResult<Unit> = runCatching {
        val (status, _) = request("/api/v1/operations/automation-rules/$ruleId", "DELETE")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getAutomationRuns(): ApiResult<List<AutomationRunDto>> = runCatching {
        val (status, response) = request("/api/v1/operations/automation-runs?limit=20")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                AutomationRunDto(item.optString("id"), item.optString("status"), item.optString("message"), item.optString("created_at"))
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    private fun parseNetworkClient(item: JSONObject) = NetworkClientDto(
        id = item.optString("id"),
        mac = item.optString("mac"),
        displayName = item.optString("display_name").takeIf { it.isNotBlank() && it != "null" },
        hostname = item.optString("hostname").takeIf { it.isNotBlank() && it != "null" },
        vendor = item.optString("vendor").takeIf { it.isNotBlank() && it != "null" },
        deviceType = item.optString("device_type", "unknown"),
        deviceTypeSource = item.optString("device_type_source", "automatic"),
        ipAddress = item.optString("ip_address").takeIf { it.isNotBlank() && it != "null" },
        currentIpv4 = item.optString("current_ipv4").takeIf { it.isNotBlank() && it != "null" },
        staticIpv4 = item.optString("static_ipv4").takeIf { it.isNotBlank() && it != "null" },
        ipv6Addresses = item.optJSONArray("ipv6_addresses")?.let { values ->
            (0 until values.length()).map(values::optString).filter(String::isNotBlank)
        } ?: emptyList(),
        networkInterface = item.optString("interface").takeIf { it.isNotBlank() && it != "null" },
        connectionType = item.optString("connection_type", "unknown"),
        connectionName = item.optString("connection_name").takeIf { it.isNotBlank() && it != "null" },
        wifiSsid = item.optString("wifi_ssid").takeIf { it.isNotBlank() && it != "null" },
        wifiBand = item.optString("wifi_band").takeIf { it.isNotBlank() && it != "null" },
        signalDbm = item.optInt("signal_dbm").takeIf { !item.isNull("signal_dbm") },
        rxBitrate = item.optLong("rx_bitrate").takeIf { !item.isNull("rx_bitrate") },
        txBitrate = item.optLong("tx_bitrate").takeIf { !item.isNull("tx_bitrate") },
        online = item.optBoolean("online"),
        presenceState = item.optString("presence_state", if (item.optBoolean("online")) "online" else "offline"),
        presenceSource = item.optString("presence_source").takeIf { it.isNotBlank() && it != "null" },
        lastObservedAt = item.optString("last_observed_at").takeIf { it.isNotBlank() && it != "null" },
        lastConfirmedAt = item.optString("last_confirmed_at").takeIf { it.isNotBlank() && it != "null" },
        isStatic = item.optBoolean("is_static"),
        profileId = item.optString("profile_id").takeIf { it.isNotBlank() && it != "null" },
        effectivePolicy = (item.optJSONObject("effective_policy") ?: JSONObject()).toJsonObject(),
        policyPreset = item.optString("policy_preset", "custom"),
        policyApplication = (item.optJSONObject("policy_application") ?: JSONObject()).let { application ->
            ClientPolicyApplicationDto(
                state = application.optString("state", "unconfigured"),
                status = application.optString("status").takeIf { it.isNotBlank() && it != "null" },
                commandId = application.optString("command_id").takeIf { it.isNotBlank() && it != "null" },
                matches = application.optBoolean("matches"),
                error = application.optString("error").takeIf { it.isNotBlank() && it != "null" },
                observed = application.optJSONObject("observed")?.toJsonObject(),
            )
        },
        traffic = item.optJSONObject("traffic")?.toJsonObject(),
        firstSeenAt = item.optString("first_seen_at").takeIf { it.isNotBlank() && it != "null" },
        lastSeenAt = item.optString("last_seen_at").takeIf { it.isNotBlank() && it != "null" },
        recentActivity = item.optJSONArray("recent_activity")?.let { events ->
            (0 until events.length()).mapNotNull { eventIndex ->
                events.optJSONObject(eventIndex)?.let { event ->
                    ClientActivityDto(
                        state = event.optString("state", "offline"),
                        source = event.optString("source").takeIf { it.isNotBlank() && it != "null" },
                        ipAddress = event.optString("ip_address").takeIf { it.isNotBlank() && it != "null" },
                        networkInterface = event.optString("interface").takeIf { it.isNotBlank() && it != "null" },
                        occurredAt = event.optString("occurred_at"),
                    )
                }
            }
        } ?: emptyList(),
    )

    private fun parseEvent(item: JSONObject) = EventDto(
        id = item.optString("id"),
        deviceId = item.optString("device_id").takeIf { it.isNotBlank() && it != "null" },
        eventType = item.optString("event_type"),
        severity = item.optString("severity"),
        source = item.optString("source"),
        title = item.optString("title"),
        message = item.optString("message"),
        status = item.optString("status"),
        occurrenceCount = item.optInt("occurrence_count", 1),
        lastOccurredAt = item.optString("last_occurred_at").takeIf { it.isNotBlank() && it != "null" },
        snoozedUntil = item.optString("snoozed_until").takeIf { it.isNotBlank() && it != "null" },
    )

    private fun parseAutomationRule(item: JSONObject) = AutomationRuleDto(
        id = item.optString("id"),
        deviceId = item.optString("device_id").takeIf { it.isNotBlank() && it != "null" },
        name = item.optString("name"),
        enabled = item.optBoolean("enabled"),
        triggerType = item.optString("trigger_type"),
        actionCommand = item.optString("action_command"),
        conditions = (item.optJSONObject("conditions") ?: JSONObject()).toJsonObject(),
        actionPayload = (item.optJSONObject("action_payload") ?: JSONObject()).toJsonObject(),
        cooldownSeconds = item.optInt("cooldown_seconds", 300),
        maxRunsPerHour = item.optInt("max_runs_per_hour", 6),
        dryRun = item.optBoolean("dry_run"),
        allowDisruptive = item.optBoolean("allow_disruptive"),
    )

    fun getManagementOptions(deviceId: String): ApiResult<ManagementOptionsDto> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/management-options")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val json = JSONObject(response)
        val catalogs = json.optJSONObject("catalogs") ?: JSONObject()
        fun strings(key: String): List<String> = json.optJSONArray(key).toStringList()
        fun catalog(key: String, valueKey: String = "value"): List<ManagementOptionDto> {
            val values = catalogs.optJSONArray(key) ?: JSONArray()
            return (0 until values.length()).map { index ->
                values.getJSONObject(index).let { item ->
                    ManagementOptionDto(
                        value = item.optString(valueKey),
                        label = item.optString("label", item.optString(valueKey)),
                        metadata = when {
                            item.has("timezone") -> item.optString("timezone")
                            item.has("prefix") -> item.optInt("prefix").toString()
                            else -> ""
                        },
                    )
                }
            }
        }
        val radios = json.optJSONArray("wifi_radios") ?: JSONArray()
        ManagementOptionsDto(
            source = json.optString("source"),
            interfaces = strings("interfaces"),
            networks = strings("networks"),
            bridges = strings("bridges"),
            firewallZones = strings("firewall_zones"),
            wifiRadios = (0 until radios.length()).map { index ->
                radios.getJSONObject(index).let { item ->
                    WifiRadioOptionDto(
                        id = item.optString("id"),
                        name = item.optString("name"),
                        band = item.optString("band"),
                        channel = item.optString("channel"),
                        country = item.optString("country"),
                        htmode = item.optString("htmode"),
                        supportedChannels = item.optJSONArray("supported_channels").toStringList(),
                    )
                }
            },
            netmasks = catalog("netmasks"),
            timezones = catalog("timezones", "zonename"),
            wifiCountries = catalog("wifi_countries"),
            fallbackWifiChannels = catalogs.optJSONArray("wifi_channels_fallback").toStringList(),
            sqmProfiles = catalog("sqm_profiles", "id").mapIndexed { index, item ->
                val raw = catalogs.optJSONArray("sqm_profiles")?.optJSONObject(index)
                item.copy(metadata = listOf(raw?.optString("qdisc"), raw?.optString("script"), raw?.optString("qdisc_options")).joinToString("|"))
            },
            clientPolicyPresets = (catalogs.optJSONArray("client_policy_presets") ?: JSONArray()).let { values ->
                (0 until values.length()).map { index ->
                    values.getJSONObject(index).let { item ->
                        ClientPolicyPresetDto(
                            id = item.optString("id"),
                            label = item.optString("label"),
                            labelEn = item.optString("label_en", item.optString("label")),
                            description = item.optString("description"),
                            descriptionEn = item.optString("description_en", item.optString("description")),
                            requiresShaping = item.optBoolean("requires_shaping"),
                            policy = (item.optJSONObject("policy") ?: JSONObject()).toJsonObject(),
                        )
                    }
                }
            },
            clientSpeedOptions = catalog("client_speed_options"),
        )
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getFirmwareCatalog(deviceId: String): ApiResult<FirmwareCatalogDto> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/firmware-catalog")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val json = JSONObject(response)
        val images = json.optJSONArray("images") ?: JSONArray()
        FirmwareCatalogDto(
            status = json.optString("status"),
            error = json.optString("error"),
            images = (0 until images.length()).map { index ->
                images.getJSONObject(index).let { item ->
                    FirmwareImageDto(
                        name = item.optString("name"),
                        label = item.optString("label"),
                        url = item.optString("url"),
                        sha256 = item.optString("sha256"),
                        model = item.optString("model"),
                    )
                }
            },
        )
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getCommands(deviceId: String): ApiResult<List<CommandDto>> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/commands")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index -> parseCommand(array.getJSONObject(index)) }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun createCommand(
        deviceId: String,
        type: String,
        payload: JsonObject,
        confirmed: Boolean = true,
    ): ApiResult<String> = runCatching {
        val (status, response) = request(
            "/api/v1/devices/$deviceId/commands",
            "POST",
            JSONObject()
                .put("command_type", type)
                .put("payload", payload.raw)
                .put("confirmed", confirmed)
                .put("idempotency_key", UUID.randomUUID().toString()),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).optString("status", "queued")
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun previewCommand(deviceId: String, type: String, payload: JsonObject): ApiResult<CommandPreviewDto> = runCatching {
        val (status, response) = request(
            "/api/v1/devices/$deviceId/commands/preview",
            "POST",
            JSONObject().put("command_type", type).put("payload", payload.raw).put("confirmed", true),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val json = JSONObject(response)
        val changes = json.optJSONArray("changes") ?: JSONArray()
        CommandPreviewDto(
            transactional = json.optBoolean("transactional"),
            configs = json.optJSONArray("configs").toStringList(),
            rollbackTimeoutSeconds = json.optInt("rollback_timeout_seconds", 90),
            connectivitySensitive = json.optBoolean("connectivity_sensitive"),
            changes = (0 until changes.length()).map { index ->
                changes.getJSONObject(index).let { item ->
                    ConfigChangeDto(
                        field = item.optString("field"),
                        current = item.optString("current", "-"),
                        proposed = item.optString("proposed", "-"),
                    )
                }
            },
            warnings = json.optJSONArray("warnings").toStringList(),
            errors = json.optJSONArray("errors").toStringList(),
            canApply = json.optBoolean("can_apply", false),
        )
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun disconnectDevice(deviceId: String): ApiResult<String> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/disconnect", "POST", JSONObject())
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).optString("status", "disconnecting")
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun deleteDevice(deviceId: String): ApiResult<String> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId", "DELETE")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).optString("status", "deleted")
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    private fun parseAgentStatus(json: JSONObject): AgentStatusDto = AgentStatusDto(
        version = json.optString("version").takeIf { it.isNotBlank() },
        status = json.optString("status").takeIf { it.isNotBlank() },
        capabilitiesVersion = if (json.has("capabilities_version") && !json.isNull("capabilities_version")) json.optInt("capabilities_version") else null,
        autoUpdateEnabled = json.optBoolean("auto_update_enabled", false),
        telemetryIntervalSeconds = if (json.has("telemetry_interval_seconds") && !json.isNull("telemetry_interval_seconds")) {
            json.optInt("telemetry_interval_seconds")
        } else {
            null
        },
        lastUpdateStatus = json.optString("last_update_status").takeIf { it.isNotBlank() },
        lastUpdateError = json.optString("last_update_error").takeIf { it.isNotBlank() },
        lastUpdateCheck = json.optString("last_update_check").takeIf { it.isNotBlank() },
        lastSuccessfulUpdate = json.optString("last_successful_update").takeIf { it.isNotBlank() },
        availableVersion = json.optString("available_version").takeIf { it.isNotBlank() },
        rollbackAvailable = json.optBoolean("rollback_available", json.optBoolean("backup_available", false)),
        updateSource = json.optString("update_source").takeIf { it.isNotBlank() },
        capabilities = json.optJSONObject("capabilities").toBooleanMap(),
        capabilityReasons = json.optJSONObject("capability_details").toCapabilityReasons(),
    )

    private fun parseHealth(json: JSONObject): HealthDto {
        val items = json.optJSONObject("items") ?: JSONObject()
        return HealthDto(
            overall = json.optString("overall", "warning"),
            items = items.keys().asSequence().associateWith { key ->
                val item = items.optJSONObject(key) ?: JSONObject()
                HealthItemDto(
                    state = item.optString("state", "unknown"),
                    label = item.optString("label"),
                    detail = item.optString("detail"),
                    observed = item.optBoolean("observed", false),
                )
            },
        )
    }

    private fun parseHardware(json: JSONObject): HardwareDto {
        val cpu = json.optJSONObject("cpu") ?: JSONObject()
        val catalog = json.optJSONObject("catalog")
        val throttling = json.optJSONObject("throttling") ?: JSONObject()
        val sensors = json.optJSONArray("sensors") ?: JSONArray()
        fun JSONObject.optionalInt(key: String): Int? =
            takeIf { has(key) && !isNull(key) }?.optInt(key)
        fun JSONObject.optionalLong(key: String): Long? =
            takeIf { has(key) && !isNull(key) }?.optLong(key)
        fun JSONObject.optionalString(key: String): String? =
            optString(key).takeIf { it.isNotBlank() && it != "null" }
        return HardwareDto(
            state = json.optString("state", "unsupported"),
            model = json.optionalString("model"),
            boardName = json.optionalString("board_name"),
            target = json.optionalString("target"),
            packageArch = json.optionalString("package_arch"),
            cpu = HardwareCpuDto(
                observedModel = cpu.optionalString("observed_model"),
                architecture = cpu.optionalString("architecture"),
                cores = cpu.optionalInt("cores"),
                currentKhz = cpu.optionalLong("current_khz"),
                maxKhz = cpu.optionalLong("max_khz"),
            ),
            catalog = catalog?.let {
                HardwareCatalogDto(
                    vendor = it.optionalString("vendor"),
                    model = it.optionalString("model"),
                    socVendor = it.optionalString("soc_vendor"),
                    socModel = it.optionalString("soc_model"),
                    cpuVendor = it.optionalString("cpu_vendor"),
                    cpuModel = it.optionalString("cpu_model"),
                    cpuArchitecture = it.optionalString("cpu_architecture"),
                    cpuCores = it.optionalInt("cpu_cores"),
                    cpuMaxMhz = it.optionalInt("cpu_max_mhz"),
                    origin = it.optionalString("origin"),
                    verified = it.optBoolean("verified", false),
                    observationCount = it.optInt("observation_count", 0),
                )
            },
            sensors = (0 until sensors.length()).mapNotNull { index ->
                sensors.optJSONObject(index)?.let { sensor ->
                    HardwareSensorDto(
                        key = sensor.optString("key"),
                        label = sensor.optString("label"),
                        role = sensor.optionalString("role"),
                        currentMilliCelsius = sensor.optionalInt("current_milli_celsius"),
                        minMilliCelsius = sensor.optionalInt("min_milli_celsius"),
                        maxMilliCelsius = sensor.optionalInt("max_milli_celsius"),
                        sampleCount = sensor.optInt("sample_count"),
                        state = sensor.optString("state", "unsupported"),
                        sourceCount = sensor.optInt("source_count", 1),
                        warningMilliCelsius = sensor.optionalInt("warning_milli_celsius"),
                        criticalMilliCelsius = sensor.optionalInt("critical_milli_celsius"),
                        headroomMilliCelsius = sensor.optionalInt("headroom_milli_celsius"),
                        thermalStatus = sensor.optString("thermal_status", "unknown"),
                    )
                }
            },
            rawSensorCount = json.optInt("raw_sensor_count", 0),
            thermalHealth = json.optString("thermal_health", "unsupported"),
            throttling = HardwareThrottlingDto(
                state = throttling.optString("state", "unsupported"),
                active = throttling.takeIf { it.has("active") && !it.isNull("active") }?.optBoolean("active"),
                thermalPressure = throttling.optionalLong("thermal_pressure"),
            ),
        )
    }

    private fun parseCommand(json: JSONObject): CommandDto = CommandDto(
        id = json.optString("id"),
        commandType = json.optString("command_type"),
        status = json.optString("status"),
        source = json.optString("source"),
        payload = (json.optJSONObject("payload") ?: JSONObject()).toJsonObject(),
        result = json.optJSONObject("result")?.toJsonObject(),
        createdAt = json.optString("created_at").takeIf { it.isNotBlank() && it != "null" },
        pickedAt = json.optString("picked_at").takeIf { it.isNotBlank() && it != "null" },
        completedAt = json.optString("completed_at").takeIf { it.isNotBlank() && it != "null" },
        expiresAt = json.optString("expires_at").takeIf { it.isNotBlank() && it != "null" },
        lastError = json.optString("last_error").takeIf { it.isNotBlank() && it != "null" },
        riskLevel = json.optString("risk_level").takeIf { it.isNotBlank() && it != "null" },
        capability = json.optString("capability").takeIf { it.isNotBlank() && it != "null" },
    )

    private fun JSONArray?.toStringList(): List<String> = this?.let { array ->
        (0 until array.length()).map { index -> array.optString(index) }
    } ?: emptyList()

    private fun JSONObject?.toBooleanMap(): Map<String, Boolean> {
        if (this == null) return emptyMap()
        return keys().asSequence().associateWith { key -> optBoolean(key, false) }
    }

    private fun JSONObject?.toCapabilityReasons(): Map<String, String> {
        if (this == null) return emptyMap()
        return keys().asSequence().associateWith { key ->
            optJSONObject(key)?.optString("reason").orEmpty()
        }
    }

    private fun toApiError(error: Throwable): ApiResult.Error {
        val http = error as? ApiHttpException
        return ApiResult.Error(
            error.message ?: "Network request failed",
            statusCode = http?.statusCode,
            code = http?.code,
            cause = error,
        )
    }

    private fun pairingErrorMessage(code: String?, status: Int): String = when (code) {
        "pairing_used" -> "This QR code has already been used"
        "pairing_expired" -> "This QR code has expired"
        "pairing_revoked" -> "This QR code was revoked"
        "pairing_rate_limited" -> "Too many attempts. Try again later"
        "pairing_server_changed" -> "The server address has changed. Create a new QR code"
        "pairing_invalid" -> "Invalid QR code"
        else -> "HTTP $status"
    }
}
