package ru.wrtmonitor.app.api.dto

import org.json.JSONArray
import org.json.JSONObject

class JsonObject internal constructor(internal val raw: JSONObject) {
    constructor() : this(JSONObject())
    constructor(source: String) : this(JSONObject(source))

    fun put(key: String, value: Any?): JsonObject = apply { raw.put(key, unwrap(value)) }
    fun optJSONObject(key: String): JsonObject? = raw.optJSONObject(key)?.let(::JsonObject)
    fun optJSONArray(key: String): JsonArray? = raw.optJSONArray(key)?.let(::JsonArray)
    fun optJsonObject(key: String): JsonObject? = optJSONObject(key)
    fun optJsonArray(key: String): JsonArray? = optJSONArray(key)
    fun optString(key: String): String = raw.optString(key)
    fun optString(key: String, fallback: String): String = raw.optString(key, fallback)
    fun getString(key: String): String = raw.getString(key)
    fun opt(key: String): Any? = wrap(raw.opt(key))
    fun optBoolean(key: String, fallback: Boolean = false): Boolean = raw.optBoolean(key, fallback)
    fun optInt(key: String, fallback: Int = 0): Int = raw.optInt(key, fallback)
    fun optLong(key: String, fallback: Long = 0): Long = raw.optLong(key, fallback)
    fun optDouble(key: String, fallback: Double = Double.NaN): Double = raw.optDouble(key, fallback)
    fun isNull(key: String): Boolean = raw.isNull(key)
    fun keys(): Iterator<String> = raw.keys()
    override fun toString(): String = raw.toString()

    companion object {
        val NULL: Any = JSONObject.NULL
    }
}

class JsonArray internal constructor(internal val raw: JSONArray) {
    constructor() : this(JSONArray())
    constructor(values: Collection<*>) : this(JSONArray(values.map(::unwrap)))
    constructor(source: String) : this(JSONArray(source))

    fun put(value: Any?): JsonArray = apply { raw.put(unwrap(value)) }
    fun length(): Int = raw.length()
    fun optJSONObject(index: Int): JsonObject? = raw.optJSONObject(index)?.let(::JsonObject)
    fun optJsonObject(index: Int): JsonObject? = optJSONObject(index)
    fun optString(index: Int): String = raw.optString(index)
    fun optString(index: Int, fallback: String): String = raw.optString(index, fallback)
    override fun toString(): String = raw.toString()
}

internal fun JSONObject.toJsonObject(): JsonObject = JsonObject(this)
internal fun JSONArray.toJsonArray(): JsonArray = JsonArray(this)

private fun unwrap(value: Any?): Any? = when (value) {
    is JsonObject -> value.raw
    is JsonArray -> value.raw
    else -> value
}

private fun wrap(value: Any?): Any? = when (value) {
    is JSONObject -> JsonObject(value)
    is JSONArray -> JsonArray(value)
    else -> value
}
