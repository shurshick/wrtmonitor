package ru.wrtmonitor.app.data

import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.wrtmonitor.app.api.ApiResult

class RouterRepositoryRealtimeTest {
    @Test
    fun parsesTelemetryEventFromServerSentEvents() = runBlocking {
        val server = MockWebServer()
        server.enqueue(
            MockResponse()
                .setHeader("Content-Type", "text/event-stream")
                .setBody(
                    "id: 9\n" +
                        "event: telemetry.updated\n" +
                        "data: {\"device_id\":\"router-1\",\"emitted_at\":\"now\"}\n\n"
                )
        )
        server.start()
        try {
            val result = withTimeout(3_000) {
                RouterRepository(server.url("/").toString(), "token")
                    .deviceEvents("router-1")
                    .first()
            }
            assertTrue(result is ApiResult.Success)
            val event = (result as ApiResult.Success).data
            assertEquals("telemetry.updated", event.type)
            assertEquals("router-1", event.deviceId)
            assertEquals("Bearer token", server.takeRequest().getHeader("Authorization"))
        } finally {
            server.shutdown()
        }
    }
}
