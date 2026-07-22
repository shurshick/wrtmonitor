package ru.wrtmonitor.app.api

import org.json.JSONArray
import org.json.JSONObject
import ru.wrtmonitor.app.api.dto.AgentStatusDto
import ru.wrtmonitor.app.api.dto.CommandDto
import ru.wrtmonitor.app.api.dto.CommandPreviewDto
import ru.wrtmonitor.app.api.dto.ClientProfileDto
import ru.wrtmonitor.app.api.dto.ConfigChangeDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.NetworkClientDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.dto.TelemetryHistoryPointDto
import java.net.HttpURLConnection
import java.net.URL

class WrtMonitorApi(private val serverUrl: String, private val accessToken: String = "") {
    private class ApiHttpException(
        val statusCode: Int,
        message: String,
        val code: String? = null,
    ) : IllegalStateException(message)

    private fun request(path: String, method: String = "GET", body: JSONObject? = null): Pair<Int, String> {
        val connection = (URL("${serverUrl.trim().trimEnd('/')}$path").openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 10_000
            readTimeout = 10_000
            if (accessToken.isNotBlank()) setRequestProperty("Authorization", "Bearer $accessToken")
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
            }
        }
        if (body != null) {
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        return status to (stream?.bufferedReader()?.use { it.readText() }.orEmpty())
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
                source = json.optString("source", "agent"),
                payload = json.optJSONObject("telemetry"),
                agent = json.optJSONObject("agent")?.let(::parseAgentStatus),
                wifi = json.optJSONObject("wifi"),
                network = json.optJSONObject("network"),
                clients = json.optJSONObject("clients"),
                system = json.optJSONObject("system"),
                services = json.optJSONObject("services"),
                alerts = json.optJSONArray("alerts"),
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
                    rxBps = point.optLong("rx_bps"),
                    txBps = point.optLong("tx_bps"),
                    rxBytes = point.optLong("rx_bytes"),
                    txBytes = point.optLong("tx_bytes"),
                    load1m = point.optDouble("load_1m"),
                    memoryPercent = point.optDouble("memory_percent"),
                    clientCount = point.optInt("client_count"),
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getNetworkClients(deviceId: String): ApiResult<List<NetworkClientDto>> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/clients")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                NetworkClientDto(
                    id = item.optString("id"),
                    mac = item.optString("mac"),
                    displayName = item.optString("display_name").takeIf { it.isNotBlank() && it != "null" },
                    hostname = item.optString("hostname").takeIf { it.isNotBlank() && it != "null" },
                    vendor = item.optString("vendor").takeIf { it.isNotBlank() && it != "null" },
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
                    isStatic = item.optBoolean("is_static"),
                    profileId = item.optString("profile_id").takeIf { it.isNotBlank() && it != "null" },
                    effectivePolicy = item.optJSONObject("effective_policy") ?: JSONObject(),
                    traffic = item.optJSONObject("traffic"),
                    firstSeenAt = item.optString("first_seen_at").takeIf { it.isNotBlank() && it != "null" },
                    lastSeenAt = item.optString("last_seen_at").takeIf { it.isNotBlank() && it != "null" },
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
                ClientProfileDto(item.optString("id"), item.optString("name"), item.optJSONObject("policy") ?: JSONObject())
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

    fun updateNetworkClient(
        deviceId: String,
        clientId: String,
        displayName: String,
        profileId: String?,
        policy: JSONObject,
    ): ApiResult<Unit> = runCatching {
        val (status, _) = request(
            "/api/v1/devices/$deviceId/clients/$clientId",
            "PUT",
            JSONObject().put("display_name", displayName).put("profile_id", profileId ?: JSONObject.NULL).put("policy", policy),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun applyNetworkClientPolicy(deviceId: String, clientId: String): ApiResult<String> = runCatching {
        val (status, response) = request(
            "/api/v1/devices/$deviceId/clients/$clientId/apply-policy",
            "POST",
            JSONObject(),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).optString("status", "queued")
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun getDeviceAgent(deviceId: String): ApiResult<AgentStatusDto> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/agent")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseAgentStatus(JSONObject(response))
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
        payload: JSONObject,
        confirmed: Boolean = true,
    ): ApiResult<String> = runCatching {
        val (status, response) = request(
            "/api/v1/devices/$deviceId/commands",
            "POST",
            JSONObject().put("command_type", type).put("payload", payload).put("confirmed", confirmed),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).optString("status", "queued")
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun previewCommand(deviceId: String, type: String, payload: JSONObject): ApiResult<CommandPreviewDto> = runCatching {
        val (status, response) = request(
            "/api/v1/devices/$deviceId/commands/preview",
            "POST",
            JSONObject().put("command_type", type).put("payload", payload).put("confirmed", true),
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

    private fun parseCommand(json: JSONObject): CommandDto = CommandDto(
        id = json.optString("id"),
        commandType = json.optString("command_type"),
        status = json.optString("status"),
        source = json.optString("source"),
        payload = json.optJSONObject("payload") ?: JSONObject(),
        result = json.optJSONObject("result"),
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
