package ru.wrtmonitor.app.data

import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import ru.wrtmonitor.app.api.WrtMonitorApi

class SessionRefreshCoordinatorTest {
    @Test
    fun concurrentUnauthorizedResponsesUseOneRefreshRequest() = runBlocking {
        val coordinator = SessionRefreshCoordinator()
        var currentToken = "expired"
        var refreshCalls = 0

        val results = coroutineScope {
            List(2) {
                async {
                    coordinator.refresh(
                        failedAccessToken = "expired",
                        currentAccessToken = { currentToken },
                        refreshRequest = {
                            refreshCalls += 1
                            WrtMonitorApi.AuthTokens("fresh", "rotated")
                        },
                        persistTokens = { currentToken = it.accessToken },
                    )
                }
            }.map { it.await() }
        }

        assertEquals(1, refreshCalls)
        assertEquals(listOf("fresh", "fresh"), results.map { it?.accessToken })
    }
}
