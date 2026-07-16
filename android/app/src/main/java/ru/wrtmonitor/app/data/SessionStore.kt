package ru.wrtmonitor.app.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class SessionStore(context: Context) {
    private val prefs = securePreferences(context)

    var serverUrl: String get() = prefs.getString("server_url", "").orEmpty(); set(value) = prefs.edit().putString("server_url", value).apply()
    var accessToken: String get() = prefs.getString("access_token", "").orEmpty(); set(value) = prefs.edit().putString("access_token", value).apply()
    fun clearSession() = prefs.edit().remove("access_token").apply()
    fun clearAll() = prefs.edit().clear().apply()

    private fun securePreferences(context: Context): SharedPreferences {
        return runCatching {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            EncryptedSharedPreferences.create(
                context,
                "wrtmonitor_secure",
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        }.getOrElse {
            context.getSharedPreferences("wrtmonitor_fallback", Context.MODE_PRIVATE)
        }
    }
}
