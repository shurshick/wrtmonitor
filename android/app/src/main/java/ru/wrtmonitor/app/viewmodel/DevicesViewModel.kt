package ru.wrtmonitor.app.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.data.RouterRepository

class DevicesViewModel(
    private val repository: RouterRepository,
) : ViewModel() {
    var state by mutableStateOf(DevicesUiState(loading = true))
        private set

    fun refresh() {
        state = state.copy(loading = true, error = null, actionError = null)
        viewModelScope.launch {
            state = when (val result = repository.devices()) {
                is ApiResult.Success -> DevicesUiState(devices = result.data)
                is ApiResult.Error -> DevicesUiState(
                    error = result.message,
                    sessionExpired = result.isUnauthorized(),
                )
            }
        }
    }

    fun disconnect(device: DeviceDto) = runAction { repository.disconnect(device.id) }

    fun delete(device: DeviceDto) = runAction { repository.delete(device.id) }

    fun reboot(device: DeviceDto) = runAction(refreshAfter = false) { repository.reboot(device.id) }

    private fun runAction(
        refreshAfter: Boolean = true,
        action: suspend () -> ApiResult<String>,
    ) {
        state = state.copy(actionError = null)
        viewModelScope.launch {
            when (val result = action()) {
                is ApiResult.Success -> if (refreshAfter) refresh()
                is ApiResult.Error -> state = state.copy(
                    actionError = result.message,
                    sessionExpired = result.isUnauthorized(),
                )
            }
        }
    }
}
