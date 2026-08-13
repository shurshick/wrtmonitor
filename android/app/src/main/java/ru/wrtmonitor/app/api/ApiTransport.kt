package ru.wrtmonitor.app.api

import org.json.JSONObject

internal class ApiHttpException(
    val statusCode: Int,
    message: String,
    val code: String? = null,
) : IllegalStateException(message)

internal class ApiTransport(
    private val serverUrl: String,
    private val accessToken: String,
) {
    fun request(path: String, method: String = "GET", body: JSONObject? = null): Pair<Int, String> {
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
}
