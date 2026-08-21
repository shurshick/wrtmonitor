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
import ru.wrtmonitor.app.api.dto.WifiExperienceDto
import ru.wrtmonitor.app.api.dto.WifiNetworkDto
import ru.wrtmonitor.app.api.dto.WifiQrDto
import ru.wrtmonitor.app.api.dto.WifiRadioDto
import ru.wrtmonitor.app.api.dto.WifiScheduleDto
import ru.wrtmonitor.app.api.dto.WifiStationDto
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
    private val transport = ApiTransport(serverUrl, accessToken)
    private val authApi = AuthApiClient(transport)
    private val operationsApi = OperationsApiClient(transport)

    private fun request(path: String, method: String = "GET", body: JSONObject? = null) =
        transport.request(path, method, body)

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

    fun login(username: String, password: String) = authApi.login(username, password)
    fun exchangeMobilePairing(pairingToken: String, clientName: String) =
        authApi.exchangeMobilePairing(pairingToken, clientName)
    fun refresh(refreshToken: String) = authApi.refresh(refreshToken)
    fun logout(refreshToken: String) = authApi.logout(refreshToken)
    fun getSessions() = authApi.getSessions()
    fun revokeSession(sessionId: String) = authApi.revokeSession(sessionId)
    fun changePassword(currentPassword: String, newPassword: String) =
        authApi.changePassword(currentPassword, newPassword)
    fun getOperationNotifications() = authApi.getOperationNotifications()

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


    fun getEvents(deviceId: String? = null) = operationsApi.getEvents(deviceId)
    fun submitFeedback(message: String, appVersion: String) = operationsApi.submitFeedback(message, appVersion)
    fun getDiagnosticReport(deviceId: String) = operationsApi.getDiagnosticReport(deviceId)
    fun acknowledgeEvent(eventId: String) = operationsApi.acknowledgeEvent(eventId)
    fun snoozeEvent(eventId: String, minutes: Int = 60) = operationsApi.snoozeEvent(eventId, minutes)
    fun getNotificationRules() = operationsApi.getNotificationRules()
    fun createInAppNotificationRule(deviceId: String, name: String) = operationsApi.createInAppNotificationRule(deviceId, name)
    fun deleteNotificationRule(ruleId: String) = operationsApi.deleteNotificationRule(ruleId)
    fun getAutomationRules() = operationsApi.getAutomationRules()
    fun getAutomationTemplates() = operationsApi.getAutomationTemplates()
    fun createAutomationFromTemplate(deviceId: String, template: AutomationTemplateDto) =
        operationsApi.createAutomationFromTemplate(deviceId, template)
    fun setAutomationEnabled(rule: AutomationRuleDto, enabled: Boolean) =
        operationsApi.setAutomationEnabled(rule, enabled)
    fun deleteAutomationRule(ruleId: String) = operationsApi.deleteAutomationRule(ruleId)
    fun getAutomationRuns() = operationsApi.getAutomationRuns()

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

    fun getWifi(deviceId: String): ApiResult<WifiExperienceDto> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/wifi")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseWifiExperience(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getWifiQr(deviceId: String, iface: String): ApiResult<WifiQrDto> = runCatching {
        val (status, response) = request(
            "/api/v1/devices/$deviceId/wifi/qr", "POST", JSONObject().put("iface", iface)
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).let {
            WifiQrDto(it.optString("ssid"), it.optString("security"), it.optString("wifi_uri"))
        }
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

}
