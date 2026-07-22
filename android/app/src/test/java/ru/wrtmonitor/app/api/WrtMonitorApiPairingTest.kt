package ru.wrtmonitor.app.api

import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class WrtMonitorApiPairingTest {
    @Test
    fun exchangesPairingTokenForNormalSession() {
        val server = MockWebServer()
        try {
            server.start()
            val baseUrl = server.url("/").toString().trimEnd('/')
            server.enqueue(
                MockResponse().setResponseCode(200).setBody(
                    """{"access_token":"access","refresh_token":"refresh","server_url":"$baseUrl","owner":{"username":"owner@example.com"}}""",
                ),
            )
            val result = WrtMonitorApi(baseUrl).exchangeMobilePairing(
                "pairing-token-value-with-at-least-32-characters",
                "Android test",
            )
            assertTrue(result is ApiResult.Success)
            val data = (result as ApiResult.Success).data
            assertEquals("access", data.tokens.accessToken)
            assertEquals("refresh", data.tokens.refreshToken)
            assertEquals("owner@example.com", data.ownerName)
            assertEquals(baseUrl, data.serverUrl)
            val request = server.takeRequest()
            assertEquals("POST", request.method)
            assertEquals("/api/v1/mobile-pairing/exchange", request.path)
            assertTrue(request.body.readUtf8().contains("pairing-token-value"))
        } finally {
            server.shutdown()
        }
    }

    @Test
    fun keepsPairingErrorCodesForTheUi() {
        for ((status, code) in listOf(
            410 to "pairing_expired",
            410 to "pairing_used",
            410 to "pairing_revoked",
            429 to "pairing_rate_limited",
        )) {
            val server = MockWebServer()
            try {
                server.start()
                val baseUrl = server.url("/").toString().trimEnd('/')
                server.enqueue(
                    MockResponse().setResponseCode(status)
                        .setBody("""{"detail":{"code":"$code"}}"""),
                )
                val result = WrtMonitorApi(baseUrl).exchangeMobilePairing(
                    "pairing-token-value-with-at-least-32-characters",
                    "Android test",
                )
                assertTrue(result is ApiResult.Error)
                assertEquals(code, (result as ApiResult.Error).code)
                assertEquals(status, result.statusCode)
            } finally {
                server.shutdown()
            }
        }
    }
}
