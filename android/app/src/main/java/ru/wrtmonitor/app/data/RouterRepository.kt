package ru.wrtmonitor.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.JsonObject
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

    suspend fun telemetryHistory(
        deviceId: String,
        range: String,
    ): ApiResult<List<TelemetryHistoryPointDto>> =
        onIo { api.getTelemetryHistory(deviceId, 120, range) }

    private suspend fun <T> onIo(block: () -> T): T = withContext(Dispatchers.IO) { block() }
}
