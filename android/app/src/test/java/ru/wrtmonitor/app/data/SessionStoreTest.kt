package ru.wrtmonitor.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class SessionStoreTest {
    @Test
    fun persistsAllPairingSessionValuesTogether() {
        val storage = RecordingStorage()
        persistSession(
            storage,
            "https://monitor.example.ru",
            "access",
            "refresh",
        )
        assertEquals("https://monitor.example.ru", storage.serverUrl)
        assertEquals("access", storage.accessToken)
        assertEquals("refresh", storage.refreshToken)
    }

    private class RecordingStorage : SessionStorage {
        var serverUrl = ""
        var accessToken = ""
        var refreshToken = ""

        override fun saveSession(
            serverUrl: String,
            accessToken: String,
            refreshToken: String,
        ) {
            this.serverUrl = serverUrl
            this.accessToken = accessToken
            this.refreshToken = refreshToken
        }
    }
}
