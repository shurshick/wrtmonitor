package ru.wrtmonitor.app.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

interface SessionStorage {
    fun saveSession(serverUrl: String, accessToken: String, refreshToken: String)
}

fun persistSession(
    storage: SessionStorage,
    serverUrl: String,
    accessToken: String,
    refreshToken: String,
) = storage.saveSession(serverUrl, accessToken, refreshToken)

class SessionStore(context: Context) : SessionStorage {
    private val prefs: SharedPreferences

    init {
        context.deleteSharedPreferences("wrtmonitor_fallback")
        prefs = securePreferences(context)
    }

    var serverUrl: String get() = prefs.getString("server_url", "").orEmpty(); set(value) = prefs.edit().putString("server_url", value).apply()
    var accessToken: String get() = prefs.getString("access_token", "").orEmpty(); set(value) = prefs.edit().putString("access_token", value).apply()
    var refreshToken: String get() = prefs.getString("refresh_token", "").orEmpty(); set(value) = prefs.edit().putString("refresh_token", value).apply()
    override fun saveSession(serverUrl: String, accessToken: String, refreshToken: String) {
        prefs.edit()
            .putString("server_url", serverUrl)
            .putString("access_token", accessToken)
            .putString("refresh_token", refreshToken)
            .apply()
    }
    fun clearSession() = prefs.edit().remove("access_token").remove("refresh_token").apply()
    fun clearAll() = prefs.edit().clear().apply()

    private fun securePreferences(context: Context): SharedPreferences {
        fun create(): SharedPreferences {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            return EncryptedSharedPreferences.create(
                context,
                "wrtmonitor_secure",
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        }
        return runCatching(::create).getOrElse {
            context.deleteSharedPreferences("wrtmonitor_secure")
            create()
        }
    }
}
