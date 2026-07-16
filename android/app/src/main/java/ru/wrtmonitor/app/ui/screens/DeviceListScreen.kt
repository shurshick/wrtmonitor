package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.ui.components.InfoRow
import ru.wrtmonitor.app.viewmodel.DevicesUiState

@Composable
fun DeviceListScreen(
    serverUrl: String,
    accessToken: String,
    refreshNonce: Int,
    modifier: Modifier = Modifier,
    onOpenDevice: (DeviceDto) -> Unit,
    onSessionExpired: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var state by remember { mutableStateOf(DevicesUiState(loading = true)) }
    var disconnectTarget by remember { mutableStateOf<DeviceDto?>(null) }
    var deleteTarget by remember { mutableStateOf<DeviceDto?>(null) }
    var actionError by remember { mutableStateOf("") }

    fun refresh() {
        state = state.copy(loading = true, error = null)
        actionError = ""
        scope.launch {
            when (val result = withContext(Dispatchers.IO) {
                WrtMonitorApi(serverUrl, accessToken).getDevices()
            }) {
                is ApiResult.Success -> state = DevicesUiState(devices = result.data)
                is ApiResult.Error -> {
                    if (result.isUnauthorized()) onSessionExpired()
                    else state = DevicesUiState(error = result.message)
                }
            }
        }
    }

    fun disconnect(device: DeviceDto) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) {
                WrtMonitorApi(serverUrl, accessToken).disconnectDevice(device.id)
            }) {
                is ApiResult.Success -> refresh()
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else actionError = result.message
            }
        }
    }

    fun deleteDevice(device: DeviceDto) {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) {
                WrtMonitorApi(serverUrl, accessToken).deleteDevice(device.id)
            }) {
                is ApiResult.Success -> refresh()
                is ApiResult.Error -> if (result.isUnauthorized()) onSessionExpired() else actionError = result.message
            }
        }
    }

    LaunchedEffect(serverUrl, accessToken, refreshNonce) { refresh() }

    Column(modifier, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(stringResource(R.string.routers), style = MaterialTheme.typography.titleLarge)
            Button({ refresh() }, enabled = !state.loading) { Text(stringResource(R.string.refresh)) }
        }
        if (actionError.isNotBlank()) {
            Text(actionError, color = MaterialTheme.colorScheme.error)
        }
        when {
            state.loading -> Box(
                Modifier.fillMaxWidth().padding(24.dp),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator() }
            state.error != null -> Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(stringResource(R.string.load_error))
                    Text(state.error.orEmpty())
                    Button({ refresh() }) { Text(stringResource(R.string.refresh)) }
                }
            }
            state.devices.isEmpty() -> Card(Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.no_routers), Modifier.padding(16.dp))
            }
            else -> LazyColumn(
                Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.devices, key = { it.id }) { device ->
                    DeviceListCard(
                        device = device,
                        onOpenDevice = onOpenDevice,
                        onDisconnect = { disconnectTarget = device },
                        onDelete = { deleteTarget = device },
                    )
                }
            }
        }
    }

    disconnectTarget?.let { device ->
        AlertDialog(
            onDismissRequest = { disconnectTarget = null },
            title = { Text(stringResource(R.string.disconnect_router_title)) },
            text = { Text(stringResource(R.string.disconnect_router_message)) },
            confirmButton = {
                TextButton(onClick = {
                    disconnectTarget = null
                    disconnect(device)
                }) { Text(stringResource(R.string.disconnect_router_action)) }
            },
            dismissButton = {
                TextButton(onClick = { disconnectTarget = null }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    deleteTarget?.let { device ->
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text(stringResource(R.string.delete_router_title)) },
            text = { Text(stringResource(R.string.delete_router_message)) },
            confirmButton = {
                TextButton(onClick = {
                    deleteTarget = null
                    deleteDevice(device)
                }) { Text(stringResource(R.string.delete_router_action)) }
            },
            dismissButton = {
                TextButton(onClick = { deleteTarget = null }) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }
}

@Composable
private fun DeviceListCard(
    device: DeviceDto,
    onOpenDevice: (DeviceDto) -> Unit,
    onDisconnect: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                device.name.ifBlank { device.hostname.ifBlank { stringResource(R.string.router) } },
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            InfoRow(stringResource(R.string.hostname), device.hostname, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.firmware), device.firmware, stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.status), device.status, stringResource(R.string.no_data))
            Button({ onOpenDevice(device) }, Modifier.fillMaxWidth()) { Text(stringResource(R.string.open)) }
            if (device.status !in setOf("disabled", "disconnecting")) {
                TextButton(onClick = onDisconnect, modifier = Modifier.align(Alignment.End)) {
                    Text(stringResource(R.string.disconnect_router_action), color = MaterialTheme.colorScheme.error)
                }
            }
            TextButton(onClick = onDelete, modifier = Modifier.align(Alignment.End)) {
                Text(stringResource(R.string.remove_from_list), color = MaterialTheme.colorScheme.error)
            }
        }
    }
}
