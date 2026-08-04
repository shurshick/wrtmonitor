package ru.wrtmonitor.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.SharedHttpClient
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.CommandDto
import ru.wrtmonitor.app.api.dto.CommandPreviewDto
import ru.wrtmonitor.app.api.dto.ClientProfileDto
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.api.dto.ManagementOptionsDto
import ru.wrtmonitor.app.api.dto.FirmwareCatalogDto
import ru.wrtmonitor.app.api.dto.NetworkClientDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.dto.TelemetryHistoryPointDto
import ru.wrtmonitor.app.api.dto.DeviceEventDto
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import org.json.JSONObject

class RouterRepository(
    private val serverUrl: String,
    private val accessToken: String,
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

    suspend fun firmwareCatalog(deviceId: String): ApiResult<FirmwareCatalogDto> =
        onIo { api.getFirmwareCatalog(deviceId) }

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

    fun deviceEvents(deviceId: String): Flow<ApiResult<DeviceEventDto>> = callbackFlow {
        val listener = object : EventSourceListener() {
            override fun onEvent(
                eventSource: EventSource,
                id: String?,
                type: String?,
                data: String,
            ) {
                runCatching {
                    val payload = JSONObject(data)
                    DeviceEventDto(
                        id = id.orEmpty(),
                        type = type ?: payload.optString("type"),
                        deviceId = payload.optString("device_id", deviceId),
                        emittedAt = payload.optString("emitted_at"),
                    )
                }.onSuccess { trySend(ApiResult.Success(it)) }
                    .onFailure { trySend(ApiResult.Error("Некорректное событие сервера", cause = it)) }
            }

            override fun onFailure(eventSource: EventSource, throwable: Throwable?, response: Response?) {
                trySend(
                    ApiResult.Error(
                        message = if (response?.code == 401) "Сессия истекла" else "Поток событий отключён",
                        statusCode = response?.code,
                        cause = throwable,
                    )
                )
                this@callbackFlow.close()
            }
        }
        val source = SharedHttpClient.eventSource(
            "${serverUrl.trim().trimEnd('/')}/api/v1/devices/$deviceId/events",
            mapOf("Authorization" to "Bearer $accessToken"),
            listener,
        )
        awaitClose { source.cancel() }
    }

    private suspend fun <T> onIo(block: () -> T): T = withContext(Dispatchers.IO) { block() }
}
