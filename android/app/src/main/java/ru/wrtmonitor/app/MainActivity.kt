package ru.wrtmonitor.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Router
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp

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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun WrtMonitorApp() {
    var tab by remember { mutableStateOf(Tab.Routers) }
    MaterialTheme {
        Scaffold(
            topBar = { TopAppBar(title = { Text("wrtmonitor") }) },
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
                when (tab) {
                    Tab.Routers -> RoutersScreen()
                    Tab.Wifi -> WifiScreen()
                    Tab.Network -> NetworkScreen()
                    Tab.System -> SystemScreen()
                    Tab.Settings -> SettingsScreen()
                }
            }
        }
    }
}

@Composable
private fun RoutersScreen() {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.routers), style = MaterialTheme.typography.titleLarge)
            Text("HomeRouter · ${stringResource(R.string.online)}")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { }) { Text(stringResource(R.string.reboot)) }
                Button(onClick = { }) { Text(stringResource(R.string.settings)) }
            }
        }
    }
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
private fun SettingsScreen() {
    var serverUrl by remember { mutableStateOf("") }
    Text(stringResource(R.string.settings), style = MaterialTheme.typography.titleLarge)
    OutlinedTextField(value = serverUrl, onValueChange = { serverUrl = it }, label = { Text(stringResource(R.string.server_url)) })
    Button(onClick = { }) { Text(stringResource(R.string.login)) }
}
