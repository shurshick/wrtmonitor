package ru.wrtmonitor.app.pairing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class MobilePairingTest {
    private val token = "A".repeat(43)

    @Test
    fun parsesStrictHttpsPayload() {
        val setup = parseMobilePairingPayload(
            """{"type":"wrtmonitor-mobile-setup","version":1,"server_url":"https://sync.example.test/","pairing_token":"$token"}""",
        )
        assertEquals("https://sync.example.test", setup.serverUrl)
        assertEquals(token, setup.pairingToken)
        assertTrue(setup.secure)
    }

    @Test
    fun allowsHttpOnlyForLocalServer() {
        val setup = parseMobilePairingPayload(
            """{"type":"wrtmonitor-mobile-setup","version":1,"server_url":"http://192.168.31.5:8088","pairing_token":"$token"}""",
        )
        assertFalse(setup.secure)
        assertThrows(MobilePairingPayloadException::class.java) {
            parseMobilePairingPayload(
                """{"type":"wrtmonitor-mobile-setup","version":1,"server_url":"http://example.test","pairing_token":"$token"}""",
            )
        }
    }

    @Test
    fun rejectsForeignOrMalformedPayloads() {
        listOf(
            "not-json",
            """{"type":"other","version":1,"server_url":"https://sync.example.test","pairing_token":"$token"}""",
            """{"type":"wrtmonitor-mobile-setup","version":2,"server_url":"https://sync.example.test","pairing_token":"$token"}""",
            """{"type":"wrtmonitor-mobile-setup","version":1,"server_url":"https://sync.example.test/path","pairing_token":"$token"}""",
            """{"type":"wrtmonitor-mobile-setup","version":1,"server_url":"https://sync.example.test","pairing_token":"short"}""",
        ).forEach { payload ->
            assertThrows(MobilePairingPayloadException::class.java) {
                parseMobilePairingPayload(payload)
            }
        }
    }
}
