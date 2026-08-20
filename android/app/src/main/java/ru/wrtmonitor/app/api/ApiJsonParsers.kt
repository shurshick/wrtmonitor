package ru.wrtmonitor.app.api

import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale
import ru.wrtmonitor.app.api.dto.*

internal fun parseNetworkClient(item: JSONObject) = NetworkClientDto(
    id = item.optString("id"),
    mac = item.optString("mac"),
    displayName = item.optString("display_name").takeIf { it.isNotBlank() && it != "null" },
    hostname = item.optString("hostname").takeIf { it.isNotBlank() && it != "null" },
    vendor = item.optString("vendor").takeIf { it.isNotBlank() && it != "null" },
    deviceType = item.optString("device_type", "unknown"),
    deviceTypeSource = item.optString("device_type_source", "automatic"),
    ipAddress = item.optString("ip_address").takeIf { it.isNotBlank() && it != "null" },
    currentIpv4 = item.optString("current_ipv4").takeIf { it.isNotBlank() && it != "null" },
    staticIpv4 = item.optString("static_ipv4").takeIf { it.isNotBlank() && it != "null" },
    ipv6Addresses = item.optJSONArray("ipv6_addresses")?.let { values ->
        (0 until values.length()).map(values::optString).filter(String::isNotBlank)
    } ?: emptyList(),
    networkInterface = item.optString("interface").takeIf { it.isNotBlank() && it != "null" },
    connectionType = item.optString("connection_type", "unknown"),
    connectionName = item.optString("connection_name").takeIf { it.isNotBlank() && it != "null" },
    wifiSsid = item.optString("wifi_ssid").takeIf { it.isNotBlank() && it != "null" },
    wifiBand = item.optString("wifi_band").takeIf { it.isNotBlank() && it != "null" },
    signalDbm = item.optInt("signal_dbm").takeIf { !item.isNull("signal_dbm") },
    rxBitrate = item.optLong("rx_bitrate").takeIf { !item.isNull("rx_bitrate") },
    txBitrate = item.optLong("tx_bitrate").takeIf { !item.isNull("tx_bitrate") },
    online = item.optBoolean("online"),
    presenceState = item.optString("presence_state", if (item.optBoolean("online")) "online" else "offline"),
    presenceSource = item.optString("presence_source").takeIf { it.isNotBlank() && it != "null" },
    lastObservedAt = item.optString("last_observed_at").takeIf { it.isNotBlank() && it != "null" },
    lastConfirmedAt = item.optString("last_confirmed_at").takeIf { it.isNotBlank() && it != "null" },
    isStatic = item.optBoolean("is_static"),
    profileId = item.optString("profile_id").takeIf { it.isNotBlank() && it != "null" },
    effectivePolicy = (item.optJSONObject("effective_policy") ?: JSONObject()).toJsonObject(),
    policyPreset = item.optString("policy_preset", "custom"),
    policyApplication = (item.optJSONObject("policy_application") ?: JSONObject()).let { application ->
        ClientPolicyApplicationDto(
            state = application.optString("state", "unconfigured"),
            status = application.optString("status").takeIf { it.isNotBlank() && it != "null" },
            commandId = application.optString("command_id").takeIf { it.isNotBlank() && it != "null" },
            matches = application.optBoolean("matches"),
            error = application.optString("error").takeIf { it.isNotBlank() && it != "null" },
            observed = application.optJSONObject("observed")?.toJsonObject(),
        )
    },
    traffic = item.optJSONObject("traffic")?.toJsonObject(),
    firstSeenAt = item.optString("first_seen_at").takeIf { it.isNotBlank() && it != "null" },
    lastSeenAt = item.optString("last_seen_at").takeIf { it.isNotBlank() && it != "null" },
    recentActivity = item.optJSONArray("recent_activity")?.let { events ->
        (0 until events.length()).mapNotNull { eventIndex ->
            events.optJSONObject(eventIndex)?.let { event ->
                ClientActivityDto(
                    state = event.optString("state", "offline"),
                    source = event.optString("source").takeIf { it.isNotBlank() && it != "null" },
                    ipAddress = event.optString("ip_address").takeIf { it.isNotBlank() && it != "null" },
                    networkInterface = event.optString("interface").takeIf { it.isNotBlank() && it != "null" },
                    occurredAt = event.optString("occurred_at"),
                )
            }
        }
    } ?: emptyList(),
)

internal fun parseEvent(item: JSONObject) = EventDto(
    id = item.optString("id"),
    deviceId = item.optString("device_id").takeIf { it.isNotBlank() && it != "null" },
    eventType = item.optString("event_type"),
    severity = item.optString("severity"),
    source = item.optString("source"),
    title = item.optString("title"),
    message = item.optString("message"),
    status = item.optString("status"),
    occurrenceCount = item.optInt("occurrence_count", 1),
    lastOccurredAt = item.optString("last_occurred_at").takeIf { it.isNotBlank() && it != "null" },
    snoozedUntil = item.optString("snoozed_until").takeIf { it.isNotBlank() && it != "null" },
)

internal fun parseAutomationRule(item: JSONObject) = AutomationRuleDto(
    id = item.optString("id"),
    deviceId = item.optString("device_id").takeIf { it.isNotBlank() && it != "null" },
    name = item.optString("name"),
    enabled = item.optBoolean("enabled"),
    triggerType = item.optString("trigger_type"),
    actionCommand = item.optString("action_command"),
    conditions = (item.optJSONObject("conditions") ?: JSONObject()).toJsonObject(),
    actionPayload = (item.optJSONObject("action_payload") ?: JSONObject()).toJsonObject(),
    cooldownSeconds = item.optInt("cooldown_seconds", 300),
    maxRunsPerHour = item.optInt("max_runs_per_hour", 6),
    dryRun = item.optBoolean("dry_run"),
    allowDisruptive = item.optBoolean("allow_disruptive"),
)


internal fun parseAgentStatus(json: JSONObject): AgentStatusDto = AgentStatusDto(
    version = json.optString("version").takeIf { it.isNotBlank() },
    status = json.optString("status").takeIf { it.isNotBlank() },
    capabilitiesVersion = if (json.has("capabilities_version") && !json.isNull("capabilities_version")) json.optInt("capabilities_version") else null,
    autoUpdateEnabled = json.optBoolean("auto_update_enabled", false),
    telemetryIntervalSeconds = if (json.has("telemetry_interval_seconds") && !json.isNull("telemetry_interval_seconds")) {
        json.optInt("telemetry_interval_seconds")
    } else {
        null
    },
    lastUpdateStatus = json.optString("last_update_status").takeIf { it.isNotBlank() },
    lastUpdateError = json.optString("last_update_error").takeIf { it.isNotBlank() },
    lastUpdateCheck = json.optString("last_update_check").takeIf { it.isNotBlank() },
    lastSuccessfulUpdate = json.optString("last_successful_update").takeIf { it.isNotBlank() },
    availableVersion = json.optString("available_version").takeIf { it.isNotBlank() },
    rollbackAvailable = json.optBoolean("rollback_available", json.optBoolean("backup_available", false)),
    updateSource = json.optString("update_source").takeIf { it.isNotBlank() },
    capabilities = json.optJSONObject("capabilities").toBooleanMap(),
    capabilityReasons = json.optJSONObject("capability_details").toCapabilityReasons(),
)

internal fun parseHealth(json: JSONObject): HealthDto {
    val items = json.optJSONObject("items") ?: JSONObject()
    return HealthDto(
        overall = json.optString("overall", "warning"),
        items = items.keys().asSequence().associateWith { key ->
            val item = items.optJSONObject(key) ?: JSONObject()
            HealthItemDto(
                state = item.optString("state", "unknown"),
                label = item.optString("label"),
                detail = item.optString("detail"),
                observed = item.optBoolean("observed", false),
            )
        },
    )
}
internal fun parseHardware(json: JSONObject): HardwareDto {
    val cpu = json.optJSONObject("cpu") ?: JSONObject()
    val catalog = json.optJSONObject("catalog")
    val throttling = json.optJSONObject("throttling") ?: JSONObject()
    val sensors = json.optJSONArray("sensors") ?: JSONArray()
    fun JSONObject.optionalInt(key: String): Int? =
        takeIf { has(key) && !isNull(key) }?.optInt(key)
    fun JSONObject.optionalLong(key: String): Long? =
        takeIf { has(key) && !isNull(key) }?.optLong(key)
    fun JSONObject.optionalString(key: String): String? =
        optString(key).takeIf { it.isNotBlank() && it != "null" }
    return HardwareDto(
        state = json.optString("state", "unsupported"),
        model = json.optionalString("model"),
        boardName = json.optionalString("board_name"),
        target = json.optionalString("target"),
        packageArch = json.optionalString("package_arch"),
        cpu = HardwareCpuDto(
            observedModel = cpu.optionalString("observed_model"),
            architecture = cpu.optionalString("architecture"),
            cores = cpu.optionalInt("cores"),
            currentKhz = cpu.optionalLong("current_khz"),
            maxKhz = cpu.optionalLong("max_khz"),
        ),
        catalog = catalog?.let {
            HardwareCatalogDto(
                vendor = it.optionalString("vendor"),
                model = it.optionalString("model"),
                socVendor = it.optionalString("soc_vendor"),
                socModel = it.optionalString("soc_model"),
                cpuVendor = it.optionalString("cpu_vendor"),
                cpuModel = it.optionalString("cpu_model"),
                cpuArchitecture = it.optionalString("cpu_architecture"),
                cpuCores = it.optionalInt("cpu_cores"),
                cpuMaxMhz = it.optionalInt("cpu_max_mhz"),
                origin = it.optionalString("origin"),
                verified = it.optBoolean("verified", false),
                observationCount = it.optInt("observation_count", 0),
            )
        },
        sensors = (0 until sensors.length()).mapNotNull { index ->
            sensors.optJSONObject(index)?.let { sensor ->
                HardwareSensorDto(
                    key = sensor.optString("key"),
                    label = sensor.optString("label"),
                    role = sensor.optionalString("role"),
                    currentMilliCelsius = sensor.optionalInt("current_milli_celsius"),
                    minMilliCelsius = sensor.optionalInt("min_milli_celsius"),
                    maxMilliCelsius = sensor.optionalInt("max_milli_celsius"),
                    sampleCount = sensor.optInt("sample_count"),
                    state = sensor.optString("state", "unsupported"),
                    sourceCount = sensor.optInt("source_count", 1),
                    warningMilliCelsius = sensor.optionalInt("warning_milli_celsius"),
                    criticalMilliCelsius = sensor.optionalInt("critical_milli_celsius"),
                    headroomMilliCelsius = sensor.optionalInt("headroom_milli_celsius"),
                    thermalStatus = sensor.optString("thermal_status", "unknown"),
                )
            }
        },
        rawSensorCount = json.optInt("raw_sensor_count", 0),
        thermalHealth = json.optString("thermal_health", "unsupported"),
        throttling = HardwareThrottlingDto(
            state = throttling.optString("state", "unsupported"),
            active = throttling.takeIf { it.has("active") && !it.isNull("active") }?.optBoolean("active"),
            thermalPressure = throttling.optionalLong("thermal_pressure"),
        ),
    )
}

internal fun parseCommand(json: JSONObject): CommandDto = CommandDto(
    id = json.optString("id"),
    commandType = json.optString("command_type"),
    status = json.optString("status"),
    source = json.optString("source"),
    payload = (json.optJSONObject("payload") ?: JSONObject()).toJsonObject(),
    result = json.optJSONObject("result")?.toJsonObject(),
    createdAt = json.optString("created_at").takeIf { it.isNotBlank() && it != "null" },
    pickedAt = json.optString("picked_at").takeIf { it.isNotBlank() && it != "null" },
    completedAt = json.optString("completed_at").takeIf { it.isNotBlank() && it != "null" },
    expiresAt = json.optString("expires_at").takeIf { it.isNotBlank() && it != "null" },
    lastError = json.optString("last_error").takeIf { it.isNotBlank() && it != "null" },
    error = json.optJSONObject("error")?.let { error ->
        CommandErrorDto(
            code = error.optString("code", "command_failed"),
            title = error.optString("title"),
            message = error.optString("message"),
            retryable = error.optBoolean("retryable"),
        )
    },
    riskLevel = json.optString("risk_level").takeIf { it.isNotBlank() && it != "null" },
    capability = json.optString("capability").takeIf { it.isNotBlank() && it != "null" },
)

internal fun JSONArray?.toStringList(): List<String> = this?.let { array ->
    (0 until array.length()).map { index -> array.optString(index) }
} ?: emptyList()

private fun JSONObject?.toBooleanMap(): Map<String, Boolean> {
    if (this == null) return emptyMap()
    return keys().asSequence().associateWith { key -> optBoolean(key, false) }
}

private fun JSONObject?.toCapabilityReasons(): Map<String, String> {
    if (this == null) return emptyMap()
    return keys().asSequence().associateWith { key ->
        optJSONObject(key)?.optString("reason").orEmpty()
    }
}

internal fun toApiError(error: Throwable): ApiResult.Error {
    val http = error as? ApiHttpException
    val russian = Locale.getDefault().language == "ru"
    val message = when (http?.statusCode) {
        401 -> if (russian) "Сессия истекла. Войдите снова." else "Session expired. Sign in again."
        403 -> if (russian) "Недостаточно прав для этого действия." else "This action is not allowed."
        404 -> if (russian) "Запрошенные данные не найдены." else "The requested data was not found."
        409 -> if (russian) "Состояние изменилось. Обновите данные и повторите." else "State changed. Refresh and try again."
        422 -> if (russian) "Проверьте введённые параметры." else "Check the entered values."
        429 -> if (russian) "Слишком много запросов. Повторите позже." else "Too many requests. Try again later."
        in 500..599 -> if (russian) "Сервер временно недоступен." else "The server is temporarily unavailable."
        null -> if (russian) "Нет соединения с сервером." else "Cannot connect to the server."
        else -> error.message
            ?.takeUnless { it.matches(Regex("HTTP \\d+")) }
            ?: if (russian) "Не удалось выполнить запрос." else "The request failed."
    }
    return ApiResult.Error(
        message,
        statusCode = http?.statusCode,
        code = http?.code,
        cause = error,
    )
}

internal fun parseWifiExperience(json: JSONObject): WifiExperienceDto {
    val radios = json.optJSONArray("radios") ?: JSONArray()
    val networks = json.optJSONArray("networks") ?: JSONArray()
    val stations = json.optJSONArray("stations") ?: JSONArray()
    return WifiExperienceDto(
        state = json.optString("state", "unsupported"),
        reason = json.optString("reason"),
        observedAt = json.optString("observed_at").takeIf(String::isNotBlank),
        radios = (0 until radios.length()).map { index ->
            val item = radios.getJSONObject(index)
            val runtime = item.optJSONObject("runtime") ?: JSONObject()
            val survey = item.optJSONObject("survey") ?: JSONObject()
            val schedule = item.optJSONObject("schedule") ?: JSONObject()
            val channels = item.optJSONArray("supported_channels") ?: JSONArray()
            val scheduleDays = schedule.optJSONArray("weekdays") ?: JSONArray()
            WifiRadioDto(
                id = item.optString("id"), name = item.optString("name"), band = item.optString("band"),
                channel = item.optString("channel", "auto"), country = item.optString("country"),
                htmode = item.optString("htmode"), txpower = item.optString("txpower"),
                configuredEnabled = item.optBoolean("configured_enabled", true),
                runtimeState = runtime.optString("state", "unsupported"),
                runtimeReason = runtime.optString("reason"),
                runtimeUp = runtime.opt("up").takeUnless { it == null || it == JSONObject.NULL } as? Boolean,
                runtimePending = runtime.opt("pending").takeUnless { it == null || it == JSONObject.NULL } as? Boolean,
                supportedChannels = (0 until channels.length()).map { channels.optString(it) },
                surveyUtilization = survey.optInt("utilization_percent").takeUnless { survey.isNull("utilization_percent") },
                surveyNoise = survey.optInt("noise_dbm").takeUnless { survey.isNull("noise_dbm") },
                schedule = WifiScheduleDto(
                    enabled = schedule.optBoolean("enabled"),
                    weekdays = (0 until scheduleDays.length()).map { scheduleDays.optString(it) },
                    start = schedule.optString("start"),
                    stop = schedule.optString("stop"),
                    activeNow = schedule.optBoolean("active_now"),
                    baseEnabled = schedule.optBoolean("base_enabled", item.optBoolean("configured_enabled", true)),
                    effectiveEnabled = schedule.optBoolean("effective_enabled", runtime.optBoolean("up")),
                ),
            )
        },
        networks = (0 until networks.length()).map { index ->
            val item = networks.getJSONObject(index)
            WifiNetworkDto(
                id = item.optString("id"), radioId = item.optString("radio_id"), band = item.optString("band"),
                ssid = item.optString("ssid"), enabled = item.optBoolean("enabled"), encryption = item.optString("encryption"),
                network = item.optString("network"), role = item.optString("role"), hidden = item.optBoolean("hidden"),
                isolate = item.optBoolean("isolate"), stationCount = item.optInt("station_count"),
            )
        },
        stations = (0 until stations.length()).map { index ->
            val item = stations.getJSONObject(index)
            WifiStationDto(
                mac = item.optString("mac"), interfaceName = item.optString("interface"), ssid = item.optString("ssid"),
                band = item.optString("band"), signal = item.optInt("signal").takeUnless { item.isNull("signal") },
                noise = item.optInt("noise").takeUnless { item.isNull("noise") },
                rxBitrate = item.opt("rx_bitrate")?.takeUnless { it == JSONObject.NULL }?.toString(),
                txBitrate = item.opt("tx_bitrate")?.takeUnless { it == JSONObject.NULL }?.toString(),
            )
        },
    )
}

