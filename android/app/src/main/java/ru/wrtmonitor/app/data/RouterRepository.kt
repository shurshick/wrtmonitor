package ru.wrtmonitor.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.SharedHttpClient
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.CommandDto
import ru.wrtmonitor.app.api.dto.CommandPreviewDto
import ru.wrtmonitor.app.api.dto.ClientProfileDto
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.api.dto.ManagementOptionsDto
import ru.wrtmonitor.app.api.dto.FirmwareCatalogDto
import ru.wrtmonitor.app.api.dto.NetworkClientDto
import ru.wrtmonitor.app.api.dto.ClientTrafficPointDto
import ru.wrtmonitor.app.api.dto.ClientActivityDto
import ru.wrtmonitor.app.api.dto.ClientConfigureResultDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.api.dto.TelemetryHistoryPointDto
import ru.wrtmonitor.app.api.dto.WifiExperienceDto
import ru.wrtmonitor.app.api.dto.WifiQrDto
import ru.wrtmonitor.app.api.dto.DeviceEventDto
import ru.wrtmonitor.app.api.dto.AutomationRuleDto
import ru.wrtmonitor.app.api.dto.AutomationRunDto
import ru.wrtmonitor.app.api.dto.AutomationTemplateDto
import ru.wrtmonitor.app.api.dto.EventDto
import ru.wrtmonitor.app.api.dto.NotificationRuleDto
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

    suspend fun wifi(deviceId: String): ApiResult<WifiExperienceDto> =
        onIo { api.getWifi(deviceId) }

    suspend fun wifiQr(deviceId: String, iface: String): ApiResult<WifiQrDto> =
        onIo { api.getWifiQr(deviceId, iface) }

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

    suspend fun client(deviceId: String, clientId: String): ApiResult<NetworkClientDto> =
        onIo { api.getNetworkClient(deviceId, clientId) }

    suspend fun clientTraffic(deviceId: String, clientId: String): ApiResult<List<ClientTrafficPointDto>> =
        onIo { api.getClientTraffic(deviceId, clientId) }

    suspend fun clientActivity(deviceId: String, clientId: String): ApiResult<List<ClientActivityDto>> =
        onIo { api.getClientActivity(deviceId, clientId) }

    suspend fun clientProfiles(deviceId: String): ApiResult<List<ClientProfileDto>> =
        onIo { api.getClientProfiles(deviceId) }

    suspend fun createClientProfile(
        deviceId: String,
        name: String,
        blocked: Boolean,
    ): ApiResult<Unit> = onIo { api.createClientProfile(deviceId, name, blocked) }

    suspend fun deleteClientProfile(deviceId: String, profileId: String): ApiResult<Unit> =
        onIo { api.deleteClientProfile(deviceId, profileId) }

    suspend fun configureClient(
        deviceId: String,
        clientId: String,
        displayName: String,
        deviceType: String,
        profileId: String?,
        policy: JsonObject,
    ): ApiResult<ClientConfigureResultDto> = onIo {
        api.configureNetworkClient(
            deviceId, clientId, displayName, deviceType, profileId, policy
        )
    }

    suspend fun deleteClient(deviceId: String, clientId: String): ApiResult<Unit> =
        onIo { api.deleteNetworkClient(deviceId, clientId) }

    suspend fun telemetryHistory(
        deviceId: String,
        range: String,
    ): ApiResult<List<TelemetryHistoryPointDto>> =
        onIo { api.getTelemetryHistory(deviceId, 120, range) }

    suspend fun events(deviceId: String): ApiResult<List<EventDto>> =
        onIo { api.getEvents(deviceId) }

    suspend fun acknowledgeEvent(eventId: String): ApiResult<EventDto> =
        onIo { api.acknowledgeEvent(eventId) }

    suspend fun snoozeEvent(eventId: String): ApiResult<EventDto> =
        onIo { api.snoozeEvent(eventId) }

    suspend fun notificationRules(): ApiResult<List<NotificationRuleDto>> =
        onIo(api::getNotificationRules)

    suspend fun createInAppNotificationRule(deviceId: String, name: String): ApiResult<Unit> =
        onIo { api.createInAppNotificationRule(deviceId, name) }

    suspend fun deleteNotificationRule(ruleId: String): ApiResult<Unit> =
        onIo { api.deleteNotificationRule(ruleId) }

    suspend fun automationRules(): ApiResult<List<AutomationRuleDto>> =
        onIo(api::getAutomationRules)

    suspend fun automationTemplates(): ApiResult<List<AutomationTemplateDto>> =
        onIo(api::getAutomationTemplates)

    suspend fun createAutomation(deviceId: String, template: AutomationTemplateDto): ApiResult<Unit> =
        onIo { api.createAutomationFromTemplate(deviceId, template) }

    suspend fun setAutomationEnabled(rule: AutomationRuleDto, enabled: Boolean): ApiResult<Unit> =
        onIo { api.setAutomationEnabled(rule, enabled) }

    suspend fun deleteAutomationRule(ruleId: String): ApiResult<Unit> =
        onIo { api.deleteAutomationRule(ruleId) }

    suspend fun automationRuns(): ApiResult<List<AutomationRunDto>> =
        onIo(api::getAutomationRuns)

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

            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                trySend(
                    ApiResult.Error(
                        message = if (response?.code == 401) "Сессия истекла" else "Поток событий отключён",
                        statusCode = response?.code,
                        cause = t,
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

    fun reconnectingDeviceEvents(
        deviceId: String,
        initialDelayMs: Long = 1_000,
        maximumDelayMs: Long = 30_000,
    ): Flow<ApiResult<DeviceEventDto>> = flow {
        var reconnectDelay = initialDelayMs.coerceAtLeast(1)
        while (true) {
            var unauthorized = false
            deviceEvents(deviceId).collect { result ->
                emit(result)
                when {
                    result is ApiResult.Success -> reconnectDelay = initialDelayMs.coerceAtLeast(1)
                    result is ApiResult.Error && result.isUnauthorized() -> unauthorized = true
                }
            }
            if (unauthorized) return@flow
            delay(reconnectDelay)
            reconnectDelay = (reconnectDelay * 2).coerceAtMost(maximumDelayMs.coerceAtLeast(1))
        }
    }

    private suspend fun <T> onIo(block: () -> T): T = withContext(Dispatchers.IO) { block() }
}
