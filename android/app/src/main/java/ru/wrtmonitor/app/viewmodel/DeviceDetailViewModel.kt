package ru.wrtmonitor.app.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.data.RouterRepository
import java.util.concurrent.atomic.AtomicInteger

class DeviceDetailViewModel(
    private val repository: RouterRepository,
    private val device: DeviceDto,
) : ViewModel() {
    var state by mutableStateOf(DeviceDetailUiState(loading = true, device = device))
        private set
    var historyRange by mutableStateOf("live")
        private set

    private val requestSerial = AtomicInteger(0)
    private var telemetryLoop: Job? = null
    private var historyLoop: Job? = null
    private var realtimeLoop: Job? = null
    private var realtimeRefresh: Job? = null

    fun start() {
        if (state.events.isEmpty()) viewModelScope.launch { refreshEvents() }
        if (telemetryLoop == null) telemetryLoop = viewModelScope.launch {
            while (true) {
                refreshTelemetry(showLoading = state.telemetry == null)
                delay(30_000)
            }
        }
        if (realtimeLoop == null) realtimeLoop = viewModelScope.launch {
            var reconnectDelay = 1_000L
            while (true) {
                var sessionExpired = false
                repository.deviceEvents(device.id).collect { result ->
                    when (result) {
                        is ApiResult.Success -> {
                            reconnectDelay = 1_000L
                            requestRealtimeRefresh()
                        }
                        is ApiResult.Error -> {
                            if (result.isUnauthorized()) {
                                state = state.copy(sessionExpired = true, error = result.message)
                                sessionExpired = true
                            }
                        }
                    }
                }
                if (sessionExpired) return@launch
                delay(reconnectDelay)
                reconnectDelay = (reconnectDelay * 2).coerceAtMost(30_000L)
            }
        }
        restartHistoryLoop()
    }

    fun selectHistoryRange(range: String) {
        if (range == historyRange) return
        historyRange = range
        restartHistoryLoop()
    }

    fun refresh() {
        viewModelScope.launch { refreshTelemetry() }
        viewModelScope.launch { refreshEvents() }
        restartHistoryLoop()
    }

    fun runQuickCommand(type: String, payload: JsonObject, successMessage: String) {
        if (state.quickActionRunning) return
        viewModelScope.launch {
            state = state.copy(quickActionRunning = true, quickActionMessage = null)
            when (val result = repository.createCommand(device.id, type, payload, true)) {
                is ApiResult.Success -> {
                    state = state.copy(
                        quickActionRunning = false,
                        quickActionMessage = successMessage,
                        quickActionError = false,
                    )
                    delay(600)
                    refreshTelemetry(showLoading = false)
                    refreshEvents()
                }
                is ApiResult.Error -> state = state.copy(
                    quickActionRunning = false,
                    quickActionMessage = result.message,
                    quickActionError = true,
                    sessionExpired = result.isUnauthorized(),
                )
            }
        }
    }

    private fun restartHistoryLoop() {
        historyLoop?.cancel()
        historyLoop = viewModelScope.launch {
            do {
                refreshHistory(historyRange)
                if (historyRange == "live") delay(30_000)
            } while (historyRange == "live")
        }
    }

    private fun requestRealtimeRefresh() {
        realtimeRefresh?.cancel()
        realtimeRefresh = viewModelScope.launch {
            delay(120)
            refreshTelemetry(showLoading = false)
            if (historyRange == "live") refreshHistory("live")
        }
    }

    private suspend fun refreshTelemetry(showLoading: Boolean = true) {
        state = state.copy(loading = showLoading && state.telemetry == null, error = null)
        when (val result = repository.latestTelemetry(device.id)) {
            is ApiResult.Success -> state = state.copy(loading = false, telemetry = result.data)
            is ApiResult.Error -> state = state.copy(
                loading = false,
                error = result.message,
                sessionExpired = result.isUnauthorized(),
            )
        }
    }

    private suspend fun refreshHistory(range: String) {
        val serial = requestSerial.incrementAndGet()
        state = state.copy(telemetryHistoryLoading = true, telemetryHistoryError = null)
        when (val result = repository.telemetryHistory(device.id, range)) {
            is ApiResult.Success -> if (serial == requestSerial.get()) {
                state = state.copy(
                    telemetryHistoryLoading = false,
                    telemetryHistory = result.data,
                    loadedTelemetryRange = range,
                )
            }
            is ApiResult.Error -> if (serial == requestSerial.get()) {
                state = state.copy(
                    telemetryHistoryLoading = false,
                    telemetryHistoryError = result.message,
                    sessionExpired = result.isUnauthorized(),
                )
            }
        }
    }

    private suspend fun refreshEvents() {
        when (val result = repository.events(device.id)) {
            is ApiResult.Success -> state = state.copy(events = result.data.take(5))
            is ApiResult.Error -> if (result.isUnauthorized()) {
                state = state.copy(sessionExpired = true, error = result.message)
            }
        }
    }
}
