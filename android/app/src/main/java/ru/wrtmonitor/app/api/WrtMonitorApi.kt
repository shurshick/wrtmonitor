package ru.wrtmonitor.app.api

import org.json.JSONArray
import org.json.JSONObject
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import java.net.HttpURLConnection
import java.net.URL

class WrtMonitorApi(private val serverUrl: String, private val accessToken: String = "") {
    private fun request(path: String, method: String = "GET", body: JSONObject? = null): Pair<Int, String> {
        val connection = (URL("${serverUrl.trim().trimEnd('/')}$path").openConnection() as HttpURLConnection).apply {
            requestMethod = method; connectTimeout = 10_000; readTimeout = 10_000
            if (accessToken.isNotBlank()) setRequestProperty("Authorization", "Bearer $accessToken")
            if (body != null) { doOutput = true; setRequestProperty("Content-Type", "application/json") }
        }
        if (body != null) connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        return status to (stream?.bufferedReader()?.use { it.readText() }.orEmpty())
    }
    fun login(username: String, password: String): ApiResult<String> = runCatching {
        val (status, response) = request("/api/v1/auth/login", "POST", JSONObject().put("username", username).put("password", password))
        if (status !in 200..299) throw IllegalStateException("HTTP $status")
        JSONObject(response).getString("access_token")
    }.fold({ ApiResult.Success(it) }, { ApiResult.Error(it.message ?: "Login failed", cause = it) })
    fun getDevices(): ApiResult<List<DeviceDto>> = runCatching {
        val (status, response) = request("/api/v1/devices")
        if (status !in 200..299) throw IllegalStateException("HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index -> array.getJSONObject(index).let { item -> DeviceDto(item.optString("id"), item.optString("name"), item.optString("hostname"), item.optString("model"), item.optString("firmware"), item.optString("status"), item.optString("last_seen_at").takeIf { value -> value.isNotBlank() && value != "null" }) } }
    }.fold({ ApiResult.Success(it) }, { ApiResult.Error(it.message ?: "Devices request failed", cause = it) })
    fun getLatestTelemetry(deviceId: String): ApiResult<TelemetryDto> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/telemetry/latest")
        if (status !in 200..299) throw IllegalStateException("HTTP $status")
        JSONObject(response).let { json -> TelemetryDto(json.optString("created_at").takeIf { it.isNotBlank() && it != "null" }, if (json.isNull("age_seconds")) null else json.optLong("age_seconds"), json.optBoolean("is_stale"), json.optString("source", "agent"), json.optJSONObject("telemetry")) }
    }.fold({ ApiResult.Success(it) }, { ApiResult.Error(it.message ?: "Telemetry request failed", cause = it) })
    fun createCommand(deviceId: String, type: String, payload: JSONObject): ApiResult<String> = runCatching {
        val (status, response) = request("/api/v1/devices/$deviceId/commands", "POST", JSONObject().put("command_type", type).put("payload", payload))
        if (status !in 200..299) throw IllegalStateException("HTTP $status")
        JSONObject(response).optString("status", "queued")
    }.fold({ ApiResult.Success(it) }, { ApiResult.Error(it.message ?: "Command request failed", cause = it) })
}
