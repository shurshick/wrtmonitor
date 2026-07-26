package ru.wrtmonitor.app.data

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import ru.wrtmonitor.app.api.WrtMonitorApi

class SessionRefreshCoordinator {
    private val mutex = Mutex()

    suspend fun refresh(
        failedAccessToken: String,
        currentAccessToken: () -> String,
        refreshRequest: suspend () -> WrtMonitorApi.AuthTokens?,
        persistTokens: (WrtMonitorApi.AuthTokens) -> Unit,
    ): WrtMonitorApi.AuthTokens? = mutex.withLock {
        val current = currentAccessToken()
        if (current.isNotBlank() && current != failedAccessToken) {
            return@withLock WrtMonitorApi.AuthTokens(current, "")
        }
        refreshRequest()?.also(persistTokens)
    }
}
