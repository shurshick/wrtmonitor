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

    fun start() {
        if (telemetryLoop == null) telemetryLoop = viewModelScope.launch {
            while (true) {
                refreshTelemetry(showLoading = state.telemetry == null)
                delay(5_000)
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
        restartHistoryLoop()
    }

    private fun restartHistoryLoop() {
        historyLoop?.cancel()
        historyLoop = viewModelScope.launch {
            do {
                refreshHistory(historyRange)
                if (historyRange == "live") delay(5_000)
            } while (historyRange == "live")
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
}
