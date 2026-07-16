package ru.wrtmonitor.app.api

import org.json.JSONArray
import org.json.JSONObject
import ru.wrtmonitor.app.api.dto.AgentStatusDto
import ru.wrtmonitor.app.api.dto.CommandDto
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import java.net.HttpURLConnection
import java.net.URL

class WrtMonitorApi(private val serverUrl: String, private val accessToken: String = "") {
    private class ApiHttpException(val statusCode: Int, message: String) : IllegalStateException(message)

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

    fun login(username: String, password: String): ApiResult<String> = runCatching {
        val (status, response) = request(
            "/api/v1/auth/login",
            "POST",
            JSONObject().put("username", username).put("password", password),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).getString("access_token")
    }.fold({ ApiResult.Success(it) }, ::toApiError)

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
            )
        }
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

    fun disconnectDevice(deviceId: String): ApiResult<String> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/disconnect", "POST", JSONObject())
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).optString("status", "disconnecting")
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun archiveDevice(deviceId: String): ApiResult<String> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/archive", "POST", JSONObject())
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        JSONObject(response).optString("status", "archived")
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    private fun parseAgentStatus(json: JSONObject): AgentStatusDto = AgentStatusDto(
        version = json.optString("version").takeIf { it.isNotBlank() },
        status = json.optString("status").takeIf { it.isNotBlank() },
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

    private fun JSONObject?.toBooleanMap(): Map<String, Boolean> {
        if (this == null) return emptyMap()
        return keys().asSequence().associateWith { key -> optBoolean(key, false) }
    }

    private fun toApiError(error: Throwable): ApiResult.Error {
        val http = error as? ApiHttpException
        return ApiResult.Error(error.message ?: "Network request failed", statusCode = http?.statusCode, cause = error)
    }
}
