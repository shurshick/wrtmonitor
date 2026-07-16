package ru.wrtmonitor.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Router
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.data.SessionStore
import ru.wrtmonitor.app.ui.screens.AdminLoginScreen
import ru.wrtmonitor.app.ui.screens.AppSettingsScreen
import ru.wrtmonitor.app.ui.screens.DeviceDetailScreen
import ru.wrtmonitor.app.ui.screens.DeviceListScreen
import ru.wrtmonitor.app.ui.screens.ClientsControlScreen
import ru.wrtmonitor.app.ui.screens.NetworkControlScreen
import ru.wrtmonitor.app.ui.screens.ServerSetupScreen
import ru.wrtmonitor.app.ui.screens.SystemControlScreen
import ru.wrtmonitor.app.ui.screens.WifiControlScreen

private enum class Tab {
    Routers,
    Clients,
    Wifi,
    Network,
    System,
    Settings,
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WrtMonitorApp() {
    val context = LocalContext.current
    val sessionStore = remember { SessionStore(context) }
    var serverUrl by remember { mutableStateOf(sessionStore.serverUrl) }
    var accessToken by remember { mutableStateOf(sessionStore.accessToken) }
    var tab by remember { mutableStateOf(Tab.Routers) }
    var selectedDevice by remember { mutableStateOf<DeviceDto?>(null) }
    var deviceListRefreshNonce by remember { mutableStateOf(0) }

    val expireSession = {
        sessionStore.clearSession()
        accessToken = ""
        selectedDevice = null
        tab = Tab.Routers
        deviceListRefreshNonce += 1
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
            onSurface = Color(0xFFE8EEF7),
        )
    ) {
        when {
            serverUrl.isBlank() -> {
                ServerSetupScreen(
                    onSave = { value ->
                        val normalized = value.trim().trimEnd('/')
                        sessionStore.serverUrl = normalized
                        serverUrl = normalized
                    }
                )
                return@MaterialTheme
            }

            accessToken.isBlank() -> {
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
        }

        BackHandler(enabled = selectedDevice != null || tab == Tab.Settings) {
            if (tab == Tab.Settings) {
                tab = Tab.Routers
            } else {
                selectedDevice = null
                tab = Tab.Routers
            }
        }

        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Image(
                                painter = painterResource(R.drawable.ic_launcher_foreground),
                                contentDescription = null,
                                modifier = Modifier.size(28.dp),
                            )
                            Text(stringResource(R.string.app_name))
                        }
                    },
                    navigationIcon = {
                        if (selectedDevice != null || tab == Tab.Settings) {
                            IconButton(onClick = {
                                if (tab == Tab.Settings) {
                                    tab = Tab.Routers
                                } else {
                                    selectedDevice = null
                                    tab = Tab.Routers
                                }
                            }) {
                                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                            }
                        }
                    },
                    actions = {
                        if (tab != Tab.Settings) {
                            IconButton(onClick = { tab = Tab.Settings }) {
                                Icon(Icons.Default.Settings, contentDescription = stringResource(R.string.settings))
                            }
                        }
                    },
                )
            },
            bottomBar = {
                NavigationBar {
                    AppNavigationItem(Tab.Routers, tab, { tab = it }, Icons.Default.Router, R.string.nav_routers, Color(0xFF6D4BC3))
                    AppNavigationItem(Tab.Clients, tab, { tab = it }, Icons.Default.People, R.string.clients, Color(0xFF2FAE79))
                    AppNavigationItem(Tab.Wifi, tab, { tab = it }, Icons.Default.Wifi, R.string.wifi, Color(0xFF008577))
                    AppNavigationItem(Tab.Network, tab, { tab = it }, Icons.Default.Router, R.string.network, Color(0xFF1565C0))
                    AppNavigationItem(Tab.System, tab, { tab = it }, Icons.Default.Settings, R.string.system, Color(0xFFD36122))
                }
            },
        ) { padding ->
            val device = selectedDevice
            if (device == null && tab == Tab.Routers) {
                DeviceListScreen(
                    serverUrl = serverUrl,
                    accessToken = accessToken,
                    refreshNonce = deviceListRefreshNonce,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp),
                    onOpenDevice = { selectedDevice = it },
                    onSessionExpired = expireSession,
                )
            } else {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    when (tab) {
                        Tab.Routers -> DeviceDetailScreen(serverUrl, accessToken, device!!, expireSession) {
                            selectedDevice = null
                            tab = Tab.Routers
                            deviceListRefreshNonce += 1
                        }

                        Tab.Clients -> DeviceTabRequired(device) { ClientsControlScreen(serverUrl, accessToken, it, expireSession) }
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
                                selectedDevice = null
                                tab = Tab.Routers
                            },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun RowScope.AppNavigationItem(
    tab: Tab,
    currentTab: Tab,
    onSelect: (Tab) -> Unit,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: Int,
    color: Color,
) {
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
            indicatorColor = color.copy(alpha = 0.16f),
        ),
    )
}

@Composable
private fun DeviceTabRequired(device: DeviceDto?, content: @Composable (DeviceDto) -> Unit) {
    if (device == null) {
        Card {
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
        overflow = TextOverflow.Ellipsis,
    )
}
