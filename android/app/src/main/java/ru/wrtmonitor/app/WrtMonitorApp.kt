package ru.wrtmonitor.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Public
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.dto.DeviceDto
import ru.wrtmonitor.app.data.SessionStore
import ru.wrtmonitor.app.data.SessionRefreshCoordinator
import ru.wrtmonitor.app.data.persistSession
import ru.wrtmonitor.app.pairing.MobilePairingPayloadException
import ru.wrtmonitor.app.pairing.MobilePairingSetup
import ru.wrtmonitor.app.pairing.normalizePairingServerUrl
import ru.wrtmonitor.app.pairing.parseMobilePairingPayload
import ru.wrtmonitor.app.ui.screens.AdminLoginScreen
import ru.wrtmonitor.app.ui.screens.AppSettingsScreen
import ru.wrtmonitor.app.ui.screens.DeviceDetailScreen
import ru.wrtmonitor.app.ui.screens.DeviceListScreen
import ru.wrtmonitor.app.ui.screens.ClientsControlScreen
import ru.wrtmonitor.app.ui.screens.NetworkControlScreen
import ru.wrtmonitor.app.ui.screens.NetworkScreenMode
import ru.wrtmonitor.app.ui.screens.OperationsScreen
import ru.wrtmonitor.app.ui.screens.PairingConfirmationScreen
import ru.wrtmonitor.app.ui.screens.QrScannerScreen
import ru.wrtmonitor.app.ui.screens.RouterSectionsScreen
import ru.wrtmonitor.app.ui.screens.ServerSetupScreen
import ru.wrtmonitor.app.ui.screens.SystemControlScreen
import ru.wrtmonitor.app.ui.screens.SystemScreenMode
import ru.wrtmonitor.app.ui.screens.WifiControlScreen
import ru.wrtmonitor.app.ui.theme.WrtMonitorTheme
import ru.wrtmonitor.app.ui.theme.WrtSizes
import ru.wrtmonitor.app.ui.theme.WrtSpacing

private enum class Tab {
    Routers,
    Clients,
    Wifi,
    Network,
    More,
    Rules,
    Vpn,
    System,
    Hardware,
    Management,
    Operations,
    Settings,
}

private val deviceStateSaver = Saver<androidx.compose.runtime.MutableState<DeviceDto?>, List<String>>(
    save = { state ->
        state.value?.let { device ->
            listOf(
                device.id,
                device.name,
                device.hostname,
                device.model,
                device.firmware,
                device.status,
                device.lastSeenAt.orEmpty(),
            )
        } ?: emptyList()
    },
    restore = { values ->
        mutableStateOf(
            if (values.isEmpty()) null else DeviceDto(
                id = values[0],
                name = values[1],
                hostname = values[2],
                model = values[3],
                firmware = values[4],
                status = values[5],
                lastSeenAt = values[6].ifBlank { null },
            ),
        )
    },
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WrtMonitorApp() {
    val context = LocalContext.current
    val sessionStore = remember { SessionStore(context) }
    val systemDarkTheme = isSystemInDarkTheme()
    var isDarkTheme by remember { mutableStateOf(sessionStore.darkTheme ?: systemDarkTheme) }
    val initialServerUrl = remember {
        sessionStore.serverUrl.takeIf(String::isNotBlank)?.let { stored ->
            runCatching { normalizePairingServerUrl(stored) }.getOrElse {
                sessionStore.clearAll()
                ""
            }
        }.orEmpty()
    }
    var serverUrl by remember { mutableStateOf(initialServerUrl) }
    var accessToken by remember { mutableStateOf(sessionStore.accessToken) }
    val refreshCoordinator = remember { SessionRefreshCoordinator() }
    var tab by rememberSaveable { mutableStateOf(Tab.Routers) }
    var selectedDevice by rememberSaveable(saver = deviceStateSaver) { mutableStateOf<DeviceDto?>(null) }
    var deviceListRefreshNonce by remember { mutableStateOf(0) }
    var qrScannerOpen by remember { mutableStateOf(false) }
    var pendingPairing by remember { mutableStateOf<MobilePairingSetup?>(null) }
    var pairingError by remember { mutableStateOf("") }

    val scope = rememberCoroutineScope()
    val clearExpiredSession = {
        sessionStore.clearSession()
        accessToken = ""
        selectedDevice = null
        tab = Tab.Routers
        deviceListRefreshNonce += 1
    }
    val expireSession: () -> Unit = {
        val refreshToken = sessionStore.refreshToken
        val failedAccessToken = accessToken
        if (refreshToken.isBlank()) {
            clearExpiredSession()
        } else {
            scope.launch {
                val tokens = refreshCoordinator.refresh(
                    failedAccessToken = failedAccessToken,
                    currentAccessToken = { sessionStore.accessToken },
                    refreshRequest = {
                        when (val result = withContext(Dispatchers.IO) {
                            WrtMonitorApi(serverUrl).refresh(refreshToken)
                        }) {
                            is ApiResult.Success -> result.data
                            is ApiResult.Error -> null
                        }
                    },
                    persistTokens = { refreshed ->
                        sessionStore.accessToken = refreshed.accessToken
                        if (refreshed.refreshToken.isNotBlank()) {
                            sessionStore.refreshToken = refreshed.refreshToken
                        }
                        accessToken = refreshed.accessToken
                        deviceListRefreshNonce += 1
                    },
                )
                if (tokens == null) {
                    clearExpiredSession()
                }
            }
        }
    }

    WrtMonitorTheme(darkTheme = isDarkTheme) {
        when {
            qrScannerOpen -> {
                QrScannerScreen(
                    onScanned = { raw ->
                        try {
                            pendingPairing = parseMobilePairingPayload(raw)
                            pairingError = ""
                        } catch (_: MobilePairingPayloadException) {
                            pairingError = context.getString(R.string.pairing_qr_invalid)
                        }
                        qrScannerOpen = false
                    },
                    onCancel = { qrScannerOpen = false },
                )
                return@WrtMonitorTheme
            }

            pendingPairing != null -> {
                val setup = pendingPairing ?: return@WrtMonitorTheme
                PairingConfirmationScreen(
                    setup = setup,
                    onConnected = { result ->
                        if (result.serverUrl != setup.serverUrl) {
                            pairingError = context.getString(R.string.pairing_qr_invalid)
                            pendingPairing = null
                        } else {
                            persistSession(
                                sessionStore,
                                result.serverUrl,
                                result.tokens.accessToken,
                                result.tokens.refreshToken,
                            )
                            serverUrl = result.serverUrl
                            accessToken = result.tokens.accessToken
                            pendingPairing = null
                            pairingError = ""
                        }
                    },
                    onCancel = { pendingPairing = null },
                )
                return@WrtMonitorTheme
            }

            serverUrl.isBlank() -> {
                ServerSetupScreen(
                    onSave = { value ->
                        try {
                            val normalized = normalizePairingServerUrl(value)
                            sessionStore.serverUrl = normalized
                            serverUrl = normalized
                            pairingError = ""
                        } catch (_: MobilePairingPayloadException) {
                            pairingError = context.getString(R.string.server_url_invalid)
                        }
                    },
                    onScanQr = {
                        pairingError = ""
                        qrScannerOpen = true
                    },
                    pairingError = pairingError,
                )
                return@WrtMonitorTheme
            }

            accessToken.isBlank() -> {
                AdminLoginScreen(
                    serverUrl = serverUrl,
                    onLogin = { tokens ->
                        persistSession(
                            sessionStore,
                            serverUrl,
                            tokens.accessToken,
                            tokens.refreshToken,
                        )
                        accessToken = tokens.accessToken
                    },
                    onChangeServer = {
                        sessionStore.clearAll()
                        serverUrl = ""
                        accessToken = ""
                    }
                )
                return@WrtMonitorTheme
            }
        }

        val navigateBack: () -> Unit = {
            when {
                tab == Tab.Settings && selectedDevice != null -> tab = Tab.More
                tab == Tab.Settings -> tab = Tab.Routers
                tab in setOf(Tab.Rules, Tab.Vpn, Tab.System, Tab.Hardware, Tab.Management, Tab.Operations) -> tab = Tab.More
                else -> {
                    selectedDevice = null
                    tab = Tab.Routers
                }
            }
        }
        BackHandler(enabled = selectedDevice != null || tab == Tab.Settings, onBack = navigateBack)

        BoxWithConstraints(Modifier.fillMaxSize()) {
        val useNavigationRail = maxWidth >= 720.dp
        Scaffold(
            contentWindowInsets = WindowInsets.safeDrawing,
            topBar = {
                TopAppBar(
                    title = {
                        val device = selectedDevice
                        if (device == null || tab == Tab.Settings) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Image(
                                    painter = painterResource(R.drawable.ic_launcher_foreground),
                                    contentDescription = null,
                                    modifier = Modifier.size(26.dp),
                                )
                                Text(stringResource(R.string.app_name))
                            }
                        } else {
                            Surface(
                                onClick = {
                                    selectedDevice = null
                                    tab = Tab.Routers
                                },
                                color = MaterialTheme.colorScheme.surfaceContainerHigh,
                                shape = MaterialTheme.shapes.medium,
                            ) {
                                Row(
                                    Modifier.padding(horizontal = WrtSpacing.sm, vertical = WrtSpacing.xs),
                                    horizontalArrangement = Arrangement.spacedBy(WrtSpacing.xs),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Column(Modifier.weight(1f, fill = false)) {
                                        Text(
                                            device.name.ifBlank { device.hostname },
                                            style = MaterialTheme.typography.titleSmall,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                        )
                                        Text(
                                            device.model,
                                            style = MaterialTheme.typography.labelSmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                        )
                                    }
                                    Icon(Icons.Default.KeyboardArrowDown, stringResource(R.string.change_router), Modifier.size(18.dp))
                                }
                            }
                        }
                    },
                    navigationIcon = {
                        if (selectedDevice != null && tab != Tab.Settings) {
                            IconButton(onClick = navigateBack) {
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
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface),
                )
            },
            bottomBar = {
                if (!useNavigationRail && selectedDevice != null && tab != Tab.Settings) {
                    NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                        AppNavigationItem(Tab.Routers, tab, { tab = it }, Icons.Default.Home, R.string.nav_overview)
                        AppNavigationItem(Tab.Clients, tab, { tab = it }, Icons.Default.People, R.string.clients)
                        AppNavigationItem(Tab.Wifi, tab, { tab = it }, Icons.Default.Wifi, R.string.wifi)
                        AppNavigationItem(Tab.Network, tab, { tab = it }, Icons.Default.Public, R.string.internet)
                        AppNavigationItem(Tab.More, tab, { tab = it }, Icons.Default.MoreHoriz, R.string.more)
                    }
                }
            },
        ) { padding ->
            Row(Modifier.fillMaxSize().padding(padding)) {
                if (useNavigationRail && selectedDevice != null && tab != Tab.Settings) {
                    AppNavigationRail(tab = tab, onSelect = { tab = it })
                }
                Box(
                    modifier = Modifier.fillMaxSize().weight(1f),
                    contentAlignment = Alignment.TopCenter,
                ) {
                val device = selectedDevice
                if (device == null && tab == Tab.Routers) {
                    DeviceListScreen(
                        serverUrl = serverUrl,
                        accessToken = accessToken,
                        refreshNonce = deviceListRefreshNonce,
                        modifier = Modifier
                            .fillMaxSize()
                            .widthIn(max = WrtSizes.contentMaxWidth)
                            .padding(WrtSpacing.md),
                        onOpenDevice = {
                            selectedDevice = it
                            tab = Tab.Routers
                        },
                        onSessionExpired = expireSession,
                    )
                } else {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .widthIn(max = WrtSizes.contentMaxWidth)
                            .padding(WrtSpacing.md)
                            .verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(WrtSpacing.sm),
                    ) {
                        key(accessToken) { when (tab) {
                        Tab.Routers -> DeviceDetailScreen(
                            serverUrl,
                            accessToken,
                            device!!,
                            expireSession,
                            onOpenClients = { tab = Tab.Clients },
                            onOpenWifi = { tab = Tab.Wifi },
                            onOpenNetwork = { tab = Tab.Network },
                            onOpenSystem = { tab = Tab.System },
                        )

                        Tab.Clients -> DeviceTabRequired(device) { ClientsControlScreen(serverUrl, accessToken, it, expireSession) }
                        Tab.Wifi -> DeviceTabRequired(device) { WifiControlScreen(serverUrl, accessToken, it, expireSession) }
                        Tab.Network -> DeviceTabRequired(device) { NetworkControlScreen(serverUrl, accessToken, it, expireSession, NetworkScreenMode.Internet) }
                        Tab.More -> RouterSectionsScreen(
                            onOpenRules = { tab = Tab.Rules },
                            onOpenVpn = { tab = Tab.Vpn },
                            onOpenSystem = { tab = Tab.System },
                            onOpenHardware = { tab = Tab.Hardware },
                            onOpenManagement = { tab = Tab.Management },
                            onOpenOperations = { tab = Tab.Operations },
                            onOpenSettings = { tab = Tab.Settings },
                        )
                        Tab.Rules -> DeviceTabRequired(device) { NetworkControlScreen(serverUrl, accessToken, it, expireSession, NetworkScreenMode.Rules) }
                        Tab.Vpn -> DeviceTabRequired(device) { NetworkControlScreen(serverUrl, accessToken, it, expireSession, NetworkScreenMode.Vpn) }
                        Tab.System -> DeviceTabRequired(device) { SystemControlScreen(serverUrl, accessToken, it, expireSession, SystemScreenMode.System) }
                        Tab.Hardware -> DeviceTabRequired(device) { SystemControlScreen(serverUrl, accessToken, it, expireSession, SystemScreenMode.Hardware) }
                        Tab.Management -> DeviceTabRequired(device) { SystemControlScreen(serverUrl, accessToken, it, expireSession, SystemScreenMode.Management) }
                        Tab.Operations -> DeviceTabRequired(device) { OperationsScreen(serverUrl, accessToken, it.id, expireSession) }
                        Tab.Settings -> AppSettingsScreen(
                            currentServerUrl = serverUrl,
                            accessToken = accessToken,
                            isDarkTheme = isDarkTheme,
                            onThemeChange = { enabled ->
                                isDarkTheme = enabled
                                sessionStore.darkTheme = enabled
                            },
                            onBack = navigateBack,
                            onSave = { value ->
                                val normalized = normalizePairingServerUrl(value)
                                sessionStore.serverUrl = normalized
                                sessionStore.clearSession()
                                serverUrl = normalized
                                accessToken = ""
                            },
                            onLogout = {
                                val refreshToken = sessionStore.refreshToken
                                scope.launch {
                                    if (refreshToken.isNotBlank()) {
                                        withContext(Dispatchers.IO) {
                                            WrtMonitorApi(serverUrl).logout(refreshToken)
                                        }
                                    }
                                    sessionStore.clearSession()
                                    accessToken = ""
                                    selectedDevice = null
                                    tab = Tab.Routers
                                }
                            },
                        )
                        } }
                    }
                }
            }
        }
        }
        }
    }
}

@Composable
private fun AppNavigationRail(tab: Tab, onSelect: (Tab) -> Unit) {
    NavigationRail(
        modifier = Modifier.widthIn(min = WrtSizes.navigationRailWidth),
        containerColor = MaterialTheme.colorScheme.surface,
    ) {
        RailItem(Tab.Routers, tab, onSelect, Icons.Default.Home, R.string.nav_overview)
        RailItem(Tab.Clients, tab, onSelect, Icons.Default.People, R.string.clients)
        RailItem(Tab.Wifi, tab, onSelect, Icons.Default.Wifi, R.string.wifi)
        RailItem(Tab.Network, tab, onSelect, Icons.Default.Public, R.string.internet)
        RailItem(Tab.More, tab, onSelect, Icons.Default.MoreHoriz, R.string.more)
    }
}

@Composable
private fun RailItem(
    tab: Tab,
    currentTab: Tab,
    onSelect: (Tab) -> Unit,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: Int,
) {
    val selected = tab == currentTab || (
        tab == Tab.More && currentTab in setOf(Tab.Rules, Tab.Vpn, Tab.System, Tab.Hardware, Tab.Management, Tab.Operations)
    )
    NavigationRailItem(
        selected = selected,
        onClick = { onSelect(tab) },
        icon = { Icon(icon, contentDescription = null) },
        label = { NavLabel(label) },
    )
}

@Composable
private fun RowScope.AppNavigationItem(
    tab: Tab,
    currentTab: Tab,
    onSelect: (Tab) -> Unit,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: Int,
) {
    val selected = tab == currentTab || (
        tab == Tab.More && currentTab in setOf(Tab.Rules, Tab.Vpn, Tab.System, Tab.Hardware, Tab.Management, Tab.Operations)
    )
    NavigationBarItem(
        selected = selected,
        onClick = { onSelect(tab) },
        icon = { Icon(icon, null) },
        label = { NavLabel(label) },
        colors = NavigationBarItemDefaults.colors(
            selectedIconColor = MaterialTheme.colorScheme.primary,
            selectedTextColor = MaterialTheme.colorScheme.primary,
            unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
            unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
            indicatorColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.14f),
        ),
    )
}

@Composable
private fun DeviceTabRequired(device: DeviceDto?, content: @Composable (DeviceDto) -> Unit) {
    if (device != null) content(device)
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
