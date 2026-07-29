package ru.wrtmonitor.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.CommandDto
import ru.wrtmonitor.app.api.dto.CommandPreviewDto
import ru.wrtmonitor.app.api.dto.ClientProfileDto
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.api.dto.ManagementOptionsDto
import ru.wrtmonitor.app.api.dto.NetworkClientDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.dto.TelemetryHistoryPointDto

class RouterRepository(
    serverUrl: String,
    accessToken: String,
) {
    private val api = WrtMonitorApi(serverUrl, accessToken)

    suspend fun devices(): ApiResult<List<DeviceDto>> = onIo(api::getDevices)

    suspend fun disconnect(deviceId: String): ApiResult<String> =
        onIo { api.disconnectDevice(deviceId) }

    suspend fun delete(deviceId: String): ApiResult<String> =
        onIo { api.deleteDevice(deviceId) }

    suspend fun reboot(deviceId: String): ApiResult<String> = onIo {
        api.createCommand(deviceId, "router.reboot", JsonObject(), confirmed = true)
    }

    suspend fun latestTelemetry(deviceId: String): ApiResult<TelemetryDto> =
        onIo { api.getLatestTelemetry(deviceId) }

    suspend fun managementOptions(deviceId: String): ApiResult<ManagementOptionsDto> =
        onIo { api.getManagementOptions(deviceId) }

    suspend fun commands(deviceId: String): ApiResult<List<CommandDto>> =
        onIo { api.getCommands(deviceId) }

    suspend fun createCommand(
        deviceId: String,
        type: String,
        payload: JsonObject,
        confirmed: Boolean = true,
    ): ApiResult<String> = onIo { api.createCommand(deviceId, type, payload, confirmed) }

    suspend fun previewCommand(
        deviceId: String,
        type: String,
        payload: JsonObject,
    ): ApiResult<CommandPreviewDto> = onIo { api.previewCommand(deviceId, type, payload) }

    suspend fun clients(deviceId: String): ApiResult<List<NetworkClientDto>> =
        onIo { api.getNetworkClients(deviceId) }

    suspend fun clientProfiles(deviceId: String): ApiResult<List<ClientProfileDto>> =
        onIo { api.getClientProfiles(deviceId) }

    suspend fun createClientProfile(
        deviceId: String,
        name: String,
        blocked: Boolean,
    ): ApiResult<Unit> = onIo { api.createClientProfile(deviceId, name, blocked) }

    suspend fun deleteClientProfile(deviceId: String, profileId: String): ApiResult<Unit> =
        onIo { api.deleteClientProfile(deviceId, profileId) }

    suspend fun updateClient(
        deviceId: String,
        clientId: String,
        displayName: String,
        profileId: String?,
        policy: JsonObject,
    ): ApiResult<Unit> = onIo {
        api.updateNetworkClient(deviceId, clientId, displayName, profileId, policy)
    }

    suspend fun applyClientPolicy(deviceId: String, clientId: String): ApiResult<String> =
        onIo { api.applyNetworkClientPolicy(deviceId, clientId) }

    suspend fun telemetryHistory(
        deviceId: String,
        range: String,
    ): ApiResult<List<TelemetryHistoryPointDto>> =
        onIo { api.getTelemetryHistory(deviceId, 120, range) }

    private suspend fun <T> onIo(block: () -> T): T = withContext(Dispatchers.IO) { block() }
}
