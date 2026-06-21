package ru.wrtmonitor.app

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Router
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.graphics.Color
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.api.dto.TelemetryDto
import ru.wrtmonitor.app.data.SessionStore
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.domain.VersionComparator
import ru.wrtmonitor.app.ui.components.InfoRow
import ru.wrtmonitor.app.ui.screens.AdminLoginScreen
import ru.wrtmonitor.app.ui.screens.ServerSetupScreen
import ru.wrtmonitor.app.ui.screens.DeviceListScreen
import ru.wrtmonitor.app.ui.screens.DeviceDetailScreen
import ru.wrtmonitor.app.ui.screens.NetworkControlScreen
import ru.wrtmonitor.app.ui.screens.SystemControlScreen
import ru.wrtmonitor.app.ui.screens.WifiControlScreen
import ru.wrtmonitor.app.ui.screens.AppSettingsScreen

private enum class Tab {
    Routers,
    Wifi,
    Network,
    System,
    Settings
}

private const val PROJECT_URL = "https://github.com/shurshick/wrtmonitor"
private const val LATEST_RELEASE_URL = "https://api.github.com/repos/shurshick/wrtmonitor/releases/latest"

private typealias RouterDevice = DeviceDto
private typealias DeviceTelemetry = TelemetryDto

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WrtMonitorApp() {
    val context = LocalContext.current
    val sessionStore = remember { SessionStore(context) }
    var serverUrl by remember { mutableStateOf(sessionStore.serverUrl) }
    var accessToken by remember { mutableStateOf(sessionStore.accessToken) }
    var tab by remember { mutableStateOf(Tab.Routers) }
    var selectedDevice by remember { mutableStateOf<RouterDevice?>(null) }
    val expireSession = {
        sessionStore.clearSession()
        accessToken = ""
        selectedDevice = null
        tab = Tab.Routers
    }
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Color(0xFF35B9D5),
            secondary = Color(0xFF73D596),
            tertiary = Color(0xFFF5BD4F),
            background = Color(0xFF0B1018),
            surface = Color(0xFF121B28),
            surfaceVariant = Color(0xFF172234),
            onPrimary = Color(0xFF041116),
            onBackground = Color(0xFFE8EEF7),
            onSurface = Color(0xFFE8EEF7)
        )
    ) {
        if (serverUrl.isBlank()) {
            ServerSetupScreen(
                onSave = { value ->
                    val normalized = value.trim().trimEnd('/')
                    sessionStore.serverUrl = normalized
                    serverUrl = normalized
                }
            )
            return@MaterialTheme
        }
        if (accessToken.isBlank()) {
            AdminLoginScreen(
                serverUrl = serverUrl,
                onLogin = { token ->
                    sessionStore.accessToken = token
                    accessToken = token
                },
                onChangeServer = {
                    sessionStore.clearAll()
                    serverUrl = ""
                    accessToken = ""
                }
            )
            return@MaterialTheme
        }
        BackHandler(enabled = selectedDevice != null) {
            selectedDevice = null
            tab = Tab.Routers
        }
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Image(
                                painter = painterResource(R.drawable.ic_launcher_foreground),
                                contentDescription = null,
                                modifier = Modifier.size(28.dp)
                            )
                            Text("WrtMonitor")
                        }
                    },
                    navigationIcon = {
                        if (selectedDevice != null) {
                            IconButton(onClick = {
                                selectedDevice = null
                                tab = Tab.Routers
                            }) {
                                Icon(Icons.AutoMirrored.Filled.ArrowBack, null)
                            }
                        }
                    }
                )
            },
            bottomBar = {
                NavigationBar {
                    AppNavigationItem(Tab.Routers, tab, { tab = it }, Icons.Default.Router, R.string.nav_routers, Color(0xFF6D4BC3))
                    AppNavigationItem(Tab.Wifi, tab, { tab = it }, Icons.Default.Wifi, R.string.wifi, Color(0xFF008577))
                    AppNavigationItem(Tab.Network, tab, { tab = it }, Icons.Default.Router, R.string.network, Color(0xFF1565C0))
                    AppNavigationItem(Tab.System, tab, { tab = it }, Icons.Default.Settings, R.string.system, Color(0xFFD36122))
                    AppNavigationItem(Tab.Settings, tab, { tab = it }, Icons.Default.Settings, R.string.nav_settings, Color(0xFF8E3A94))
                }
            }
        ) { padding ->
            val device = selectedDevice
            if (device == null && tab == Tab.Routers) {
                DeviceListScreen(
                    serverUrl = serverUrl,
                    accessToken = accessToken,
                    modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                    onOpenDevice = { selectedDevice = it },
                    onSessionExpired = expireSession
                )
            } else {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    when (tab) {
                        Tab.Routers -> DeviceDetailScreen(serverUrl, accessToken, device!!, expireSession)
                        Tab.Wifi -> DeviceTabRequired(device) { WifiControlScreen(serverUrl, accessToken, it, expireSession) }
                        Tab.Network -> DeviceTabRequired(device) { NetworkControlScreen(serverUrl, accessToken, it, expireSession) }
                        Tab.System -> DeviceTabRequired(device) { SystemControlScreen(serverUrl, accessToken, it, expireSession) }
                        Tab.Settings -> AppSettingsScreen(
                            currentServerUrl = serverUrl,
                            onSave = { value ->
                                val normalized = value.trim().trimEnd('/')
                                sessionStore.serverUrl = normalized
                                sessionStore.clearSession()
                                serverUrl = normalized
                                accessToken = ""
                            },
                            onLogout = {
                                sessionStore.clearSession()
                                accessToken = ""
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun RowScope.AppNavigationItem(tab: Tab, currentTab: Tab, onSelect: (Tab) -> Unit, icon: androidx.compose.ui.graphics.vector.ImageVector, label: Int, color: Color) {
    val selected = tab == currentTab
    NavigationBarItem(
        selected = selected,
        onClick = { onSelect(tab) },
        icon = { Icon(icon, null, tint = color) },
        label = { NavLabel(label) },
        colors = NavigationBarItemDefaults.colors(
            selectedIconColor = color,
            selectedTextColor = color,
            unselectedIconColor = color.copy(alpha = 0.72f),
            unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
            indicatorColor = color.copy(alpha = 0.16f)
        )
    )
}

@Composable
private fun DeviceTabRequired(device: RouterDevice?, content: @Composable (RouterDevice) -> Unit) {
    if (device == null) {
        Card(Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.select_router_hint), modifier = Modifier.padding(16.dp))
        }
    } else {
        content(device)
    }
}

@Composable
private fun NavLabel(resId: Int) {
    Text(
        text = stringResource(resId),
        style = MaterialTheme.typography.labelSmall,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable
private fun FirstRunScreen(onSave: (String) -> Unit) {
    var serverUrl by remember { mutableStateOf("") }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text("WrtMonitor", style = MaterialTheme.typography.headlineMedium)
        Text(stringResource(R.string.first_run_server_prompt))
        OutlinedTextField(
            value = serverUrl,
            onValueChange = { serverUrl = it },
            label = { Text(stringResource(R.string.server_url)) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        Button(
            onClick = { onSave(serverUrl) },
            enabled = serverUrl.trim().startsWith("http://") || serverUrl.trim().startsWith("https://")
        ) {
            Text(stringResource(R.string.save))
        }
    }
}

@Composable
private fun LoginScreen(serverUrl: String, onLogin: (String) -> Unit, onChangeServer: () -> Unit) {
    val scope = kotlinx.coroutines.CoroutineScope(Dispatchers.Main)
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text("WrtMonitor", style = MaterialTheme.typography.headlineMedium)
        Text(serverUrl)
        OutlinedTextField(
            value = username,
            onValueChange = { username = it },
            label = { Text(stringResource(R.string.admin_username)) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text(stringResource(R.string.admin_password)) },
            modifier = Modifier.fillMaxWidth(),
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true
        )
        if (error.isNotBlank()) {
            Text(error)
        }
        Button(
            onClick = {
                loading = true
                error = ""
                scope.launch {
                    runCatching {
                        withContext(Dispatchers.IO) { loginAdmin(serverUrl, username, password) }
                    }.onSuccess { token ->
                        loading = false
                        onLogin(token)
                    }.onFailure {
                        loading = false
                        error = it.message ?: "Login failed"
                    }
                }
            },
            enabled = !loading && username.isNotBlank() && password.isNotBlank()
        ) {
            Text(stringResource(R.string.login))
        }
        Button(onClick = onChangeServer, enabled = !loading) {
            Text(stringResource(R.string.change_server))
        }
    }
}

private fun loginAdmin(serverUrl: String, username: String, password: String): String {
    return when (val result = WrtMonitorApi(serverUrl).login(username, password)) {
        is ApiResult.Success -> result.data
        is ApiResult.Error -> throw IllegalStateException(result.message, result.cause)
    }
}

@Composable
private fun RoutersScreen(serverUrl: String, accessToken: String, modifier: Modifier = Modifier, onOpenDevice: (RouterDevice) -> Unit) {
    val scope = rememberCoroutineScope()
    var devices by remember { mutableStateOf<List<RouterDevice>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf("") }

    fun refresh() {
        loading = true
        error = ""
        scope.launch {
            runCatching {
                withContext(Dispatchers.IO) { fetchDevices(serverUrl, accessToken) }
            }.onSuccess {
                devices = it
                loading = false
            }.onFailure {
                error = it.message ?: "Failed to load devices"
                loading = false
            }
        }
    }

    LaunchedEffect(serverUrl, accessToken) {
        refresh()
    }

    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.routers), style = MaterialTheme.typography.titleLarge)
            Button(onClick = { refresh() }, enabled = !loading) {
                Text(stringResource(R.string.refresh))
            }
        }
        when {
            loading -> {
                Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            error.isNotBlank() -> {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(stringResource(R.string.load_error))
                        Text(error)
                        Button(onClick = { refresh() }) { Text(stringResource(R.string.refresh)) }
                    }
                }
            }
            devices.isEmpty() -> {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(stringResource(R.string.no_routers))
                    }
                }
            }
            else -> {
                LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(devices, key = { it.id }) { device ->
                        RouterCard(device, onOpenDevice)
                    }
                }
            }
        }
    }
}

@Composable
private fun RouterCard(device: RouterDevice, onOpenDevice: (RouterDevice) -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        device.name.ifBlank { device.hostname.ifBlank { stringResource(R.string.router) } },
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        device.model.ifBlank { device.hostname.ifBlank { stringResource(R.string.no_data) } },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                StatusText(device.status)
            }
            InfoRow(stringResource(R.string.hostname), device.hostname)
            InfoRow(stringResource(R.string.firmware), shortFirmware(device.firmware))
            InfoRow(stringResource(R.string.last_seen), formatTimestamp(device.lastSeenAt))
            Button(onClick = { onOpenDevice(device) }, modifier = Modifier.align(Alignment.End)) {
                Text(stringResource(R.string.open))
            }
        }
    }
}

@Composable
private fun DeviceScreen(serverUrl: String, accessToken: String, device: RouterDevice) {
    val scope = rememberCoroutineScope()
    var telemetry by remember(device.id) { mutableStateOf<DeviceTelemetry?>(null) }
    var loading by remember(device.id) { mutableStateOf(true) }
    var error by remember(device.id) { mutableStateOf("") }

    fun refresh() {
        loading = true
        error = ""
        scope.launch {
            runCatching {
                withContext(Dispatchers.IO) { fetchLatestTelemetry(serverUrl, accessToken, device.id) }
            }.onSuccess {
                telemetry = it
                loading = false
            }.onFailure {
                error = it.message ?: "Failed to load telemetry"
                loading = false
            }
        }
    }

    LaunchedEffect(serverUrl, accessToken, device.id) {
        refresh()
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
                    Text(
                        device.name.ifBlank { device.hostname.ifBlank { stringResource(R.string.router) } },
                        style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier.weight(1f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    StatusText(device.status)
                }
                InfoRow(stringResource(R.string.model), device.model)
                InfoRow(stringResource(R.string.firmware), shortFirmware(device.firmware))
                InfoRow(stringResource(R.string.last_seen), formatTimestamp(device.lastSeenAt))
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.telemetry), style = MaterialTheme.typography.titleLarge)
            Button(onClick = { refresh() }, enabled = !loading) { Text(stringResource(R.string.refresh)) }
        }
        when {
            loading -> Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            error.isNotBlank() -> Text(error)
            telemetry?.payload == null -> Text(stringResource(R.string.no_data))
            else -> TelemetryCard(telemetry!!)
        }
    }
}

@Composable
private fun TelemetryCard(telemetry: DeviceTelemetry) {
    var showRaw by remember { mutableStateOf(false) }
    val payload = telemetry.payload ?: JSONObject()
    val system = payload.optJSONObject("system")
    val memory = system?.optJSONObject("memory")
    val wifi = payload.optJSONObject("wifi")
    val network = payload.optJSONObject("network")
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            InfoRow(stringResource(R.string.updated_at), formatTimestamp(telemetry.createdAt))
            InfoRow(stringResource(R.string.age), telemetry.ageSeconds?.let { stringResource(R.string.seconds_value, it) } ?: stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.source), telemetry.source)
            if (telemetry.isStale) {
                Text(
                    stringResource(R.string.stale_telemetry),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error
                )
            }
            InfoRow(stringResource(R.string.uptime), formatDuration(system?.optLong("uptime", 0) ?: 0))
            InfoRow(stringResource(R.string.load), system?.optString("load") ?: stringResource(R.string.no_data))
            if (memory != null) {
                InfoRow(stringResource(R.string.memory), "${memory.optLong("available_kb", 0) / 1024} / ${memory.optLong("total_kb", 0) / 1024} MB")
            }
            InfoRow(stringResource(R.string.network), if (network != null) stringResource(R.string.available) else stringResource(R.string.no_data))
            InfoRow(stringResource(R.string.wifi), if (wifi?.optBoolean("available", false) == true) stringResource(R.string.available) else stringResource(R.string.no_data))
            WifiRadios(wifi)
            TextButton(onClick = { showRaw = !showRaw }, modifier = Modifier.align(Alignment.End)) {
                Text(if (showRaw) stringResource(R.string.hide_raw_telemetry) else stringResource(R.string.show_raw_telemetry))
            }
            if (showRaw) {
                Text(
                    payload.toString(2),
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}

@Composable
private fun StatusText(status: String) {
    Text(
        text = status.ifBlank { stringResource(R.string.no_data) },
        style = MaterialTheme.typography.labelMedium,
        color = if (status.equals("online", ignoreCase = true)) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = Modifier.widthIn(max = 96.dp)
    )
}

@Composable
private fun WifiRadios(wifi: JSONObject?) {
    val radios = wifi?.optJSONArray("radios") ?: JSONArray()
    if (radios.length() == 0) {
        InfoRow(stringResource(R.string.wifi_radios), stringResource(R.string.no_data))
        return
    }
    Text(stringResource(R.string.wifi_radios), style = MaterialTheme.typography.titleMedium)
    for (index in 0 until radios.length()) {
        val radio = radios.optJSONObject(index) ?: continue
        val ssids = radio.optJSONArray("ssid") ?: JSONArray()
        val ssidText = (0 until ssids.length()).joinToString(", ") { ssids.optString(it) }
        Text(
            "${radio.optString("name", "radio$index")}: " +
                "${if (radio.optBoolean("up", false)) stringResource(R.string.online) else "offline"}, " +
                "SSID: ${ssidText.ifBlank { stringResource(R.string.no_data) }}"
        )
    }
}

private fun fetchDevices(serverUrl: String, accessToken: String): List<RouterDevice> {
    return when (val result = WrtMonitorApi(serverUrl, accessToken).getDevices()) { is ApiResult.Success -> result.data; is ApiResult.Error -> throw IllegalStateException(result.message, result.cause) }
}

private fun fetchLatestTelemetry(serverUrl: String, accessToken: String, deviceId: String): DeviceTelemetry {
    return when (val result = WrtMonitorApi(serverUrl, accessToken).getLatestTelemetry(deviceId)) { is ApiResult.Success -> result.data; is ApiResult.Error -> throw IllegalStateException(result.message, result.cause) }
}

private fun sendDeviceCommand(serverUrl: String, accessToken: String, deviceId: String, commandType: String, payload: JSONObject): String {
    return when (val result = WrtMonitorApi(serverUrl, accessToken).createCommand(deviceId, commandType, payload)) { is ApiResult.Success -> result.data; is ApiResult.Error -> throw IllegalStateException(result.message, result.cause) }
}

private fun formatTimestamp(value: String?): String {
    if (value.isNullOrBlank()) return ""
    val main = value.substringBefore(".").substringBefore("+").substringBefore("Z")
    val parts = main.split("T")
    if (parts.size != 2) return value
    val date = parts[0].split("-")
    if (date.size != 3) return value
    val time = parts[1].split(":").take(2).joinToString(":")
    return "${date[2]}.${date[1]}.${date[0]} $time UTC"
}

private fun shortFirmware(value: String): String {
    if (value.isBlank()) return ""
    return value.replace(Regex("\\s+r\\d+-[0-9a-fA-F]+"), "")
}

private fun formatDuration(seconds: Long): String {
    if (seconds <= 0) return "0"
    val days = seconds / 86_400
    val hours = (seconds % 86_400) / 3_600
    val minutes = (seconds % 3_600) / 60
    return when {
        days > 0 -> "${days}d ${hours}h"
        hours > 0 -> "${hours}h ${minutes}m"
        else -> "${minutes}m"
    }
}

@Composable
private fun WifiScreen(serverUrl: String, accessToken: String, device: RouterDevice) {
    val scope = rememberCoroutineScope()
    val loadError = stringResource(R.string.load_error)
    val queuedMessage = stringResource(R.string.command_queued)
    val commandFailed = stringResource(R.string.command_failed)
    var telemetry by remember(device.id) { mutableStateOf<DeviceTelemetry?>(null) }
    var ssid by remember(device.id) { mutableStateOf("") }
    var enabled by remember(device.id) { mutableStateOf(false) }
    var loading by remember(device.id) { mutableStateOf(true) }
    var message by remember(device.id) { mutableStateOf("") }

    fun refresh() {
        loading = true
        scope.launch {
            runCatching { withContext(Dispatchers.IO) { fetchLatestTelemetry(serverUrl, accessToken, device.id) } }
                .onSuccess { snapshot ->
                    telemetry = snapshot
                    val radio = snapshot.payload?.optJSONObject("wifi")?.optJSONArray("radios")?.optJSONObject(0)
                    if (ssid.isBlank()) ssid = radio?.optJSONArray("ssid")?.optString(0).orEmpty()
                    enabled = radio?.optBoolean("up", false) ?: false
                    loading = false
                }
                .onFailure {
                    message = it.message ?: loadError
                    loading = false
                }
        }
    }

    fun queue(type: String, payload: JSONObject) {
        message = ""
        scope.launch {
            runCatching { withContext(Dispatchers.IO) { sendDeviceCommand(serverUrl, accessToken, device.id, type, payload) } }
                .onSuccess { message = queuedMessage }
                .onFailure { message = it.message ?: commandFailed }
        }
    }

    LaunchedEffect(device.id) { refresh() }
    val wifi = telemetry?.payload?.optJSONObject("wifi")
    val available = wifi?.optBoolean("available", false) == true

    Text(stringResource(R.string.wifi), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            InfoRow(stringResource(R.string.router), device.name.ifBlank { device.hostname })
            InfoRow(stringResource(R.string.status), if (available) stringResource(R.string.available) else stringResource(R.string.wifi_unavailable))
            if (available) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(stringResource(R.string.wifi_enabled))
                    Switch(
                        checked = enabled,
                        onCheckedChange = { value ->
                            enabled = value
                            queue("wifi.set_enabled", JSONObject().put("enabled", value))
                        }
                    )
                }
                OutlinedTextField(
                    value = ssid,
                    onValueChange = { ssid = it },
                    label = { Text("SSID") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                Button(
                    onClick = { queue("wifi.set_ssid", JSONObject().put("ssid", ssid)) },
                    enabled = ssid.isNotBlank()
                ) { Text(stringResource(R.string.apply_ssid)) }
                WifiRadios(wifi)
            }
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.primary)
            TextButton(onClick = { refresh() }, modifier = Modifier.align(Alignment.End), enabled = !loading) {
                Text(stringResource(R.string.refresh))
            }
        }
    }
}

@Composable
private fun NetworkScreen(serverUrl: String, accessToken: String, device: RouterDevice) {
    val scope = rememberCoroutineScope()
    val loadError = stringResource(R.string.load_error)
    val queuedMessage = stringResource(R.string.command_queued)
    val commandFailed = stringResource(R.string.command_failed)
    var telemetry by remember(device.id) { mutableStateOf<DeviceTelemetry?>(null) }
    var loading by remember(device.id) { mutableStateOf(true) }
    var message by remember(device.id) { mutableStateOf("") }

    fun refresh() {
        loading = true
        scope.launch {
            runCatching { withContext(Dispatchers.IO) { fetchLatestTelemetry(serverUrl, accessToken, device.id) } }
                .onSuccess { telemetry = it; loading = false }
                .onFailure { message = it.message ?: loadError; loading = false }
        }
    }

    fun requestInterfaces() {
        scope.launch {
            runCatching { withContext(Dispatchers.IO) { sendDeviceCommand(serverUrl, accessToken, device.id, "network.interfaces", JSONObject()) } }
                .onSuccess { message = queuedMessage }
                .onFailure { message = it.message ?: commandFailed }
        }
    }

    LaunchedEffect(device.id) { refresh() }
    val network = telemetry?.payload?.optJSONObject("network")
    Text(stringResource(R.string.network), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            InfoRow(stringResource(R.string.router), device.name.ifBlank { device.hostname })
            InfoRow(stringResource(R.string.status), if (network != null) stringResource(R.string.available) else stringResource(R.string.no_data))
            NetworkInterfaces(network)
            if (network == null && !loading) {
                Text(stringResource(R.string.network_no_details), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.primary)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { requestInterfaces() }) { Text(stringResource(R.string.request_interfaces)) }
                TextButton(onClick = { refresh() }, enabled = !loading) { Text(stringResource(R.string.refresh)) }
            }
        }
    }
}

@Composable
private fun NetworkInterfaces(network: JSONObject?) {
    val interfaces = network?.optJSONArray("interface") ?: JSONArray()
    if (interfaces.length() == 0) return
    Text(stringResource(R.string.network_interfaces), style = MaterialTheme.typography.titleSmall)
    for (index in 0 until minOf(interfaces.length(), 8)) {
        val item = interfaces.optJSONObject(index) ?: continue
        val name = item.optString("interface", "interface$index")
        val state = if (item.optBoolean("up", false)) stringResource(R.string.online) else stringResource(R.string.offline)
        val device = item.optString("l3_device").ifBlank { item.optString("device") }
        InfoRow(name, listOf(state, device).filter { it.isNotBlank() }.joinToString(" • "))
    }
}

@Composable
private fun SystemScreen(serverUrl: String, accessToken: String, device: RouterDevice) {
    val scope = rememberCoroutineScope()
    val loadError = stringResource(R.string.load_error)
    val rebootQueued = stringResource(R.string.reboot_queued)
    val commandFailed = stringResource(R.string.command_failed)
    var telemetry by remember(device.id) { mutableStateOf<DeviceTelemetry?>(null) }
    var loading by remember(device.id) { mutableStateOf(true) }
    var message by remember(device.id) { mutableStateOf("") }
    var confirmReboot by remember { mutableStateOf(false) }

    fun refresh() {
        loading = true
        scope.launch {
            runCatching { withContext(Dispatchers.IO) { fetchLatestTelemetry(serverUrl, accessToken, device.id) } }
                .onSuccess { telemetry = it; loading = false }
                .onFailure { message = it.message ?: loadError; loading = false }
        }
    }

    fun queueReboot() {
        confirmReboot = false
        scope.launch {
            runCatching { withContext(Dispatchers.IO) { sendDeviceCommand(serverUrl, accessToken, device.id, "router.reboot", JSONObject()) } }
                .onSuccess { message = rebootQueued }
                .onFailure { message = it.message ?: commandFailed }
        }
    }

    LaunchedEffect(device.id) { refresh() }
    val system = telemetry?.payload?.optJSONObject("system")
    val board = telemetry?.payload?.optJSONObject("board")
    Text(stringResource(R.string.system), style = MaterialTheme.typography.titleLarge)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            InfoRow(stringResource(R.string.router), device.name.ifBlank { device.hostname })
            InfoRow(stringResource(R.string.uptime), formatDuration(system?.optLong("uptime", 0) ?: 0))
            InfoRow(stringResource(R.string.load), system?.optString("load"))
            InfoRow(stringResource(R.string.model), (board?.optString("model") ?: device.model).ifBlank { device.model })
            InfoRow(stringResource(R.string.firmware), (board?.optString("release") ?: "").ifBlank { shortFirmware(device.firmware) })
            if (message.isNotBlank()) Text(message, color = MaterialTheme.colorScheme.primary)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { confirmReboot = true }) { Text(stringResource(R.string.reboot)) }
                TextButton(onClick = { refresh() }, enabled = !loading) { Text(stringResource(R.string.refresh)) }
            }
        }
    }
    if (confirmReboot) {
        AlertDialog(
            onDismissRequest = { confirmReboot = false },
            title = { Text(stringResource(R.string.reboot_confirm_title)) },
            text = { Text(stringResource(R.string.reboot_confirm_message)) },
            confirmButton = { TextButton(onClick = { queueReboot() }) { Text(stringResource(R.string.reboot)) } },
            dismissButton = { TextButton(onClick = { confirmReboot = false }) { Text(stringResource(R.string.cancel)) } }
        )
    }
}

@Composable
private fun SettingsScreen(currentServerUrl: String, onSave: (String) -> Unit, onLogout: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var serverUrl by remember(currentServerUrl) { mutableStateOf(currentServerUrl) }
    var showAbout by remember { mutableStateOf(false) }
    var updateState by remember { mutableStateOf<UpdateState?>(null) }
    var checkingUpdate by remember { mutableStateOf(false) }

    if (showAbout) {
        AboutAppScreen(
            updateState = updateState,
            checkingUpdate = checkingUpdate,
            onBack = { showAbout = false },
            onOpenProject = { openUrl(context, PROJECT_URL) },
            onCheckUpdates = {
                checkingUpdate = true
                updateState = null
                scope.launch {
                    updateState = runCatching {
                        withContext(Dispatchers.IO) {
                            checkForUpdate(appVersionName(context))
                        }
                    }.getOrElse { UpdateState.Error }
                    checkingUpdate = false
                }
            },
            onOpenRelease = { url -> openUrl(context, url) }
        )
        return
    }

    Text(stringResource(R.string.settings), style = MaterialTheme.typography.titleLarge)
    OutlinedTextField(
        value = serverUrl,
        onValueChange = { serverUrl = it },
        label = { Text(stringResource(R.string.server_url)) },
        modifier = Modifier.fillMaxWidth(),
        singleLine = true
    )
    Button(onClick = { onSave(serverUrl) }) { Text(stringResource(R.string.save)) }
    TextButton(onClick = onLogout) { Text(stringResource(R.string.logout)) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.about_app), style = MaterialTheme.typography.titleMedium)
            Text(
                stringResource(R.string.about_app_summary),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Button(onClick = { showAbout = true }, modifier = Modifier.align(Alignment.End)) {
                Text(stringResource(R.string.open))
            }
        }
    }
}

private sealed interface UpdateState {
    data class UpToDate(val latestVersion: String) : UpdateState
    data class Available(val latestVersion: String, val releaseUrl: String) : UpdateState
    data object Error : UpdateState
}

@Composable
private fun AboutAppScreen(
    updateState: UpdateState?,
    checkingUpdate: Boolean,
    onBack: () -> Unit,
    onOpenProject: () -> Unit,
    onCheckUpdates: () -> Unit,
    onOpenRelease: (String) -> Unit
) {
    BackHandler(onBack = onBack)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
            }
            Text(stringResource(R.string.about_app), style = MaterialTheme.typography.titleLarge)
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("wrtmonitor", style = MaterialTheme.typography.titleLarge)
                InfoRow(stringResource(R.string.app_version), appVersionName(LocalContext.current))
                Text(
                    stringResource(R.string.copyright),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Button(onClick = onOpenProject, modifier = Modifier.align(Alignment.End)) {
                    Text(stringResource(R.string.project_page))
                }
            }
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.updates), style = MaterialTheme.typography.titleMedium)
                when (val state = updateState) {
                    null -> Text(
                        stringResource(R.string.update_check_hint),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    is UpdateState.UpToDate -> Text(stringResource(R.string.app_up_to_date, state.latestVersion))
                    is UpdateState.Available -> {
                        Text(stringResource(R.string.update_available, state.latestVersion))
                        Button(onClick = { onOpenRelease(state.releaseUrl) }, modifier = Modifier.align(Alignment.End)) {
                            Text(stringResource(R.string.download_update))
                        }
                    }
                    UpdateState.Error -> Text(
                        stringResource(R.string.update_check_error),
                        color = MaterialTheme.colorScheme.error
                    )
                }
                Button(onClick = onCheckUpdates, enabled = !checkingUpdate, modifier = Modifier.align(Alignment.End)) {
                    if (checkingUpdate) {
                        CircularProgressIndicator(
                            modifier = Modifier.widthIn(max = 20.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(stringResource(R.string.check_updates))
                    }
                }
            }
        }
    }
}

private fun appVersionName(context: android.content.Context): String =
    context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: ""

private fun openUrl(context: android.content.Context, url: String) {
    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
}

private fun checkForUpdate(currentVersion: String): UpdateState {
    val connection = (URL(LATEST_RELEASE_URL).openConnection() as HttpURLConnection).apply {
        requestMethod = "GET"
        connectTimeout = 10_000
        readTimeout = 10_000
        setRequestProperty("Accept", "application/vnd.github+json")
        setRequestProperty("User-Agent", "wrtmonitor-android")
    }
    val status = connection.responseCode
    val response = if (status in 200..299) {
        connection.inputStream.bufferedReader().use { it.readText() }
    } else {
        ""
    }
    if (status !in 200..299) throw IllegalStateException("HTTP $status")
    val release = JSONObject(response)
    val latestVersion = release.optString("tag_name").removePrefix("v")
    val releaseUrl = release.optString("html_url")
    return if (VersionComparator.compare(latestVersion, currentVersion) > 0) {
        UpdateState.Available(latestVersion, releaseUrl)
    } else {
        UpdateState.UpToDate(latestVersion)
    }
}
