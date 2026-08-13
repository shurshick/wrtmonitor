package ru.wrtmonitor.app.api

import org.json.JSONArray
import org.json.JSONObject

internal class AuthApiClient(private val transport: ApiTransport) {
    fun login(username: String, password: String): ApiResult<WrtMonitorApi.AuthTokens> = runCatching {
        val (status, response) = transport.request(
            "/api/v1/auth/login",
            "POST",
            JSONObject().put("username", username).put("password", password),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseAuthTokens(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun exchangeMobilePairing(
        pairingToken: String,
        clientName: String,
    ): ApiResult<WrtMonitorApi.PairingResult> = runCatching {
        val (status, response) = transport.request(
            "/api/v1/mobile-pairing/exchange",
            "POST",
            JSONObject().put("pairing_token", pairingToken).put("client_name", clientName),
        )
        if (status !in 200..299) {
            val code = runCatching {
                JSONObject(response).optJSONObject("detail")?.optString("code")
            }.getOrNull()
            throw ApiHttpException(status, pairingErrorMessage(code, status), code)
        }
        val json = JSONObject(response)
        WrtMonitorApi.PairingResult(
            tokens = parseAuthTokens(json),
            serverUrl = json.getString("server_url").trimEnd('/'),
            ownerName = json.optJSONObject("owner")?.optString("username").orEmpty(),
        )
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun refresh(refreshToken: String): ApiResult<WrtMonitorApi.AuthTokens> = runCatching {
        val (status, response) = transport.request(
            "/api/v1/auth/refresh", "POST", JSONObject().put("refresh_token", refreshToken),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        parseAuthTokens(JSONObject(response))
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    fun logout(refreshToken: String): ApiResult<Unit> = runCatching {
        val (status, _) = transport.request(
            "/api/v1/auth/logout", "POST", JSONObject().put("refresh_token", refreshToken),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getSessions(): ApiResult<List<WrtMonitorApi.UserSessionDto>> = runCatching {
        val (status, response) = transport.request("/api/v1/auth/sessions?active_only=true")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                WrtMonitorApi.UserSessionDto(
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
        val (status, _) = transport.request("/api/v1/auth/sessions/$sessionId", "DELETE")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun changePassword(currentPassword: String, newPassword: String): ApiResult<Unit> = runCatching {
        val (status, _) = transport.request(
            "/api/v1/auth/change-password",
            "POST",
            JSONObject()
                .put("current_password", currentPassword)
                .put("new_password", newPassword)
                .put("new_password_confirm", newPassword),
        )
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
    }.fold({ ApiResult.Success(Unit) }, ::toApiError)

    fun getOperationNotifications(): ApiResult<List<WrtMonitorApi.OperationNotificationDto>> = runCatching {
        val (status, response) = transport.request("/api/v1/operations/notifications")
        if (status !in 200..299) throw ApiHttpException(status, "HTTP $status")
        val array = JSONArray(response)
        (0 until array.length()).map { index ->
            array.getJSONObject(index).let { item ->
                WrtMonitorApi.OperationNotificationDto(
                    severity = item.optString("severity"),
                    title = item.optString("title"),
                    message = item.optString("message"),
                )
            }
        }
    }.fold({ ApiResult.Success(it) }, ::toApiError)

    private fun parseAuthTokens(json: JSONObject) = WrtMonitorApi.AuthTokens(
        accessToken = json.getString("access_token"),
        refreshToken = json.getString("refresh_token"),
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
