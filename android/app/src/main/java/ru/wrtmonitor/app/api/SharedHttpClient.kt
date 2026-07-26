package ru.wrtmonitor.app.api

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

internal object SharedHttpClient {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    fun request(
        url: String,
        method: String = "GET",
        body: JSONObject? = null,
        headers: Map<String, String> = emptyMap(),
    ): Pair<Int, String> {
        val requestBody = body?.toString()?.toRequestBody(jsonMediaType)
        val builder = Request.Builder().url(url)
        headers.forEach(builder::header)
        when (method) {
            "GET" -> builder.get()
            "DELETE" -> builder.delete(requestBody)
            else -> builder.method(method, requestBody ?: ByteArray(0).toRequestBody(null))
        }
        client.newCall(builder.build()).execute().use { response ->
            return response.code to response.body?.string().orEmpty()
        }
    }
}
