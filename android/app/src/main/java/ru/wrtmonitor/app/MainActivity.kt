package ru.wrtmonitor.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Router
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { WrtMonitorApp() }
    }
}

private enum class Tab {
    Routers,
    Wifi,
    Network,
    System,
    Settings
}

private const val PREFS_NAME = "wrtmonitor"
private const val PREF_SERVER_URL = "server_url"
private const val PREF_ACCESS_TOKEN = "access_token"

private data class RouterDevice(
    val id: String,
    val name: String,
    val hostname: String,
    val model: String,
    val firmware: String,
    val status: String,
    val lastSeenAt: String?
)

private data class DeviceTelemetry(
    val createdAt: String?,
    val payload: JSONObject?
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun WrtMonitorApp() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences(PREFS_NAME, 0) }
    var serverUrl by remember { mutableStateOf(prefs.getString(PREF_SERVER_URL, "") ?: "") }
    var accessToken by remember { mutableStateOf(prefs.getString(PREF_ACCESS_TOKEN, "") ?: "") }
    var tab by remember { mutableStateOf(Tab.Routers) }
    var selectedDevice by remember { mutableStateOf<RouterDevice?>(null) }
    MaterialTheme {
        if (serverUrl.isBlank()) {
            FirstRunScreen(
                onSave = { value ->
                    val normalized = value.trim().trimEnd('/')
                    prefs.edit().putString(PREF_SERVER_URL, normalized).apply()
                    serverUrl = normalized
                }
            )
            return@MaterialTheme
        }
        if (accessToken.isBlank()) {
            LoginScreen(
                serverUrl = serverUrl,
                onLogin = { token ->
                    prefs.edit().putString(PREF_ACCESS_TOKEN, token).apply()
                    accessToken = token
                },
                onChangeServer = {
                    prefs.edit().remove(PREF_SERVER_URL).remove(PREF_ACCESS_TOKEN).apply()
                    serverUrl = ""
                    accessToken = ""
                }
            )
            return@MaterialTheme
        }
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text(selectedDevice?.name?.ifBlank { selectedDevice?.hostname ?: "wrtmonitor" } ?: "wrtmonitor") },
                    navigationIcon = {
                        if (selectedDevice != null) {
                            Button(onClick = { selectedDevice = null }) {
                                Icon(Icons.Default.ArrowBack, null)
                            }
                        }
                    }
                )
            },
            bottomBar = {
                NavigationBar {
                    NavigationBarItem(selected = tab == Tab.Routers, onClick = { tab = Tab.Routers }, icon = { Icon(Icons.Default.Router, null) }, label = { Text(stringResource(R.string.routers)) })
                    NavigationBarItem(selected = tab == Tab.Wifi, onClick = { tab = Tab.Wifi }, icon = { Icon(Icons.Default.Wifi, null) }, label = { Text(stringResource(R.string.wifi)) })
                    NavigationBarItem(selected = tab == Tab.Network, onClick = { tab = Tab.Network }, icon = { Icon(Icons.Default.Router, null) }, label = { Text(stringResource(R.string.network)) })
                    NavigationBarItem(selected = tab == Tab.System, onClick = { tab = Tab.System }, icon = { Icon(Icons.Default.Settings, null) }, label = { Text(stringResource(R.string.system)) })
                    NavigationBarItem(selected = tab == Tab.Settings, onClick = { tab = Tab.Settings }, icon = { Icon(Icons.Default.Settings, null) }, label = { Text(stringResource(R.string.settings)) })
                }
            }
        ) { padding ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                val device = selectedDevice
                if (device != null) {
                    DeviceScreen(serverUrl, accessToken, device)
                } else {
                    when (tab) {
                        Tab.Routers -> RoutersScreen(serverUrl, accessToken) { selectedDevice = it }
                        Tab.Wifi -> WifiScreen()
                        Tab.Network -> NetworkScreen()
                        Tab.System -> SystemScreen()
                        Tab.Settings -> SettingsScreen(serverUrl) { value ->
                            val normalized = value.trim().trimEnd('/')
                            prefs.edit().putString(PREF_SERVER_URL, normalized).remove(PREF_ACCESS_TOKEN).apply()
                            serverUrl = normalized
                            accessToken = ""
                        }
                    }
                }
            }
        }
    }
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
        Text("wrtmonitor", style = MaterialTheme.typography.headlineMedium)
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
        Text("wrtmonitor", style = MaterialTheme.typography.headlineMedium)
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
    val url = URL("${serverUrl.trim().trimEnd('/')}/api/v1/auth/login")
    val connection = (url.openConnection() as HttpURLConnection).apply {
        requestMethod = "POST"
        connectTimeout = 10_000
        readTimeout = 10_000
        doOutput = true
        setRequestProperty("Content-Type", "application/json")
    }
    val body = JSONObject()
        .put("username", username)
        .put("password", password)
        .toString()
    connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
    val status = connection.responseCode
    val stream = if (status in 200..299) connection.inputStream else connection.errorStream
    val response = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
    if (status !in 200..299) {
        throw IllegalStateException("HTTP $status")
    }
    return JSONObject(response).getString("access_token")
}

@Composable
private fun RoutersScreen(serverUrl: String, accessToken: String, onOpenDevice: (RouterDevice) -> Unit) {
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

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
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
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(device.name.ifBlank { device.hostname.ifBlank { stringResource(R.string.router) } }, style = MaterialTheme.typography.titleMedium)
            Text("${stringResource(R.string.status)}: ${device.status}")
            if (device.hostname.isNotBlank()) Text("Hostname: ${device.hostname}")
            if (device.model.isNotBlank()) Text("${stringResource(R.string.model)}: ${device.model}")
            if (device.firmware.isNotBlank()) Text("${stringResource(R.string.firmware)}: ${device.firmware}")
            Text("${stringResource(R.string.last_seen)}: ${device.lastSeenAt ?: stringResource(R.string.no_data)}")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { onOpenDevice(device) }) { Text(stringResource(R.string.open)) }
                Button(onClick = { }) { Text(stringResource(R.string.reboot)) }
                Button(onClick = { }) { Text(stringResource(R.string.settings)) }
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
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(device.name.ifBlank { device.hostname.ifBlank { stringResource(R.string.router) } }, style = MaterialTheme.typography.titleLarge)
                Text("${stringResource(R.string.status)}: ${device.status}")
                if (device.model.isNotBlank()) Text("${stringResource(R.string.model)}: ${device.model}")
                if (device.firmware.isNotBlank()) Text("${stringResource(R.string.firmware)}: ${device.firmware}")
                Text("${stringResource(R.string.last_seen)}: ${device.lastSeenAt ?: stringResource(R.string.no_data)}")
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
    val payload = telemetry.payload ?: JSONObject()
    val system = payload.optJSONObject("system")
    val wifi = payload.optJSONObject("wifi")
    val network = payload.optJSONObject("network")
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("${stringResource(R.string.updated_at)}: ${telemetry.createdAt ?: stringResource(R.string.no_data)}")
            Text("${stringResource(R.string.uptime)}: ${system?.optLong("uptime", 0) ?: 0}")
            Text("${stringResource(R.string.load)}: ${system?.optString("load") ?: stringResource(R.string.no_data)}")
            Text("${stringResource(R.string.wifi)}: ${wifi?.optBoolean("available", false) ?: false}")
            Text("${stringResource(R.string.network)}: ${network?.optBoolean("available", true) ?: true}")
            Text(payload.toString(2))
        }
    }
}

private fun fetchDevices(serverUrl: String, accessToken: String): List<RouterDevice> {
    val url = URL("${serverUrl.trim().trimEnd('/')}/api/v1/devices")
    val connection = (url.openConnection() as HttpURLConnection).apply {
        requestMethod = "GET"
        connectTimeout = 10_000
        readTimeout = 10_000
        setRequestProperty("Authorization", "Bearer $accessToken")
    }
    val status = connection.responseCode
    val stream = if (status in 200..299) connection.inputStream else connection.errorStream
    val response = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
    if (status !in 200..299) {
        throw IllegalStateException("HTTP $status")
    }
    val array = JSONArray(response)
    return (0 until array.length()).map { index ->
        val item = array.getJSONObject(index)
        RouterDevice(
            id = item.optString("id"),
            name = item.optString("name"),
            hostname = item.optString("hostname"),
            model = item.optString("model"),
            firmware = item.optString("firmware"),
            status = item.optString("status"),
            lastSeenAt = item.optString("last_seen_at").takeIf { it.isNotBlank() && it != "null" }
        )
    }
}

private fun fetchLatestTelemetry(serverUrl: String, accessToken: String, deviceId: String): DeviceTelemetry {
    val url = URL("${serverUrl.trim().trimEnd('/')}/api/v1/devices/$deviceId/telemetry/latest")
    val connection = (url.openConnection() as HttpURLConnection).apply {
        requestMethod = "GET"
        connectTimeout = 10_000
        readTimeout = 10_000
        setRequestProperty("Authorization", "Bearer $accessToken")
    }
    val status = connection.responseCode
    val stream = if (status in 200..299) connection.inputStream else connection.errorStream
    val response = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
    if (status !in 200..299) {
        throw IllegalStateException("HTTP $status")
    }
    val json = JSONObject(response)
    return DeviceTelemetry(
        createdAt = json.optString("created_at").takeIf { it.isNotBlank() && it != "null" },
        payload = json.optJSONObject("telemetry")
    )
}

@Composable
private fun WifiScreen() {
    var ssid by remember { mutableStateOf("Home Wi-Fi") }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.wifi), style = MaterialTheme.typography.titleLarge)
            OutlinedTextField(value = ssid, onValueChange = { ssid = it }, label = { Text("SSID") })
            Button(onClick = { }) { Text(stringResource(R.string.apply)) }
        }
    }
}

@Composable
private fun NetworkScreen() {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.network), style = MaterialTheme.typography.titleLarge)
            Text("LAN / WAN")
            Button(onClick = { }) { Text(stringResource(R.string.apply)) }
        }
    }
}

@Composable
private fun SystemScreen() {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.system), style = MaterialTheme.typography.titleLarge)
            Button(onClick = { }) { Text(stringResource(R.string.reboot)) }
        }
    }
}

@Composable
private fun SettingsScreen(currentServerUrl: String, onSave: (String) -> Unit) {
    var serverUrl by remember(currentServerUrl) { mutableStateOf(currentServerUrl) }
    Text(stringResource(R.string.settings), style = MaterialTheme.typography.titleLarge)
    OutlinedTextField(
        value = serverUrl,
        onValueChange = { serverUrl = it },
        label = { Text(stringResource(R.string.server_url)) },
        modifier = Modifier.fillMaxWidth(),
        singleLine = true
    )
    Button(onClick = { onSave(serverUrl) }) { Text(stringResource(R.string.save)) }
    Button(onClick = { }) { Text(stringResource(R.string.login)) }
}
