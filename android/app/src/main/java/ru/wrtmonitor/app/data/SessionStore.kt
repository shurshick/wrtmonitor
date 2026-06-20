package ru.wrtmonitor.app.data

import android.content.Context

class SessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("wrtmonitor", Context.MODE_PRIVATE)
    var serverUrl: String get() = prefs.getString("server_url", "").orEmpty(); set(value) = prefs.edit().putString("server_url", value).apply()
    var accessToken: String get() = prefs.getString("access_token", "").orEmpty(); set(value) = prefs.edit().putString("access_token", value).apply()
    fun clearSession() = prefs.edit().remove("access_token").apply()
    fun clearAll() = prefs.edit().clear().apply()
}
