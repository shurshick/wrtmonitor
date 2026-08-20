package ru.wrtmonitor.app.api

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.After
import org.junit.Before
import org.junit.Test
import java.util.Locale

class ApiJsonParsersTest {
    private lateinit var originalLocale: Locale

    @Before
    fun useRussianLocale() {
        originalLocale = Locale.getDefault()
        Locale.setDefault(Locale.forLanguageTag("ru-RU"))
    }

    @After
    fun restoreLocale() {
        Locale.setDefault(originalLocale)
    }

    @Test
    fun parsesStructuredCommandError() {
        val command = parseCommand(
            JSONObject(
                """{
                    "id":"command-1",
                    "command_type":"wifi.set_ssid",
                    "status":"failed",
                    "source":"android",
                    "payload":{},
                    "error":{
                        "code":"post_condition_failed",
                        "title":"Роутер не подтвердил изменение",
                        "message":"SSID остался прежним",
                        "retryable":true
                    }
                }"""
            )
        )
        assertEquals("post_condition_failed", command.error?.code)
        assertEquals("Роутер не подтвердил изменение", command.error?.title)
        assertTrue(command.error?.retryable == true)
    }

    @Test
    fun replacesRawHttpErrorWithUserMessage() {
        val result = toApiError(ApiHttpException(401, "HTTP 401"))
        assertEquals("Сессия истекла. Войдите снова.", result.message)
        assertEquals(401, result.statusCode)
    }
}
