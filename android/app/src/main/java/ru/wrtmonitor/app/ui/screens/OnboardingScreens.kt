package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi

@Composable
fun ServerSetupScreen(onSave: (String) -> Unit) {
    var serverUrl by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("WrtMonitor", style = MaterialTheme.typography.headlineMedium)
        Text(stringResource(R.string.first_run_server_prompt))
        OutlinedTextField(serverUrl, { serverUrl = it }, label = { Text(stringResource(R.string.server_url)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        Button(onClick = { onSave(serverUrl) }, enabled = serverUrl.isNotBlank()) { Text(stringResource(R.string.save)) }
    }
}

@Composable
fun AdminLoginScreen(serverUrl: String, onLogin: (String) -> Unit, onChangeServer: () -> Unit) {
    var username by remember { mutableStateOf("") }; var password by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }; var loading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.login), style = MaterialTheme.typography.headlineMedium)
        OutlinedTextField(username, { username = it }, label = { Text("Администратор") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(password, { password = it }, label = { Text("Пароль") }, modifier = Modifier.fillMaxWidth(), visualTransformation = PasswordVisualTransformation(), singleLine = true)
        if (error.isNotBlank()) Text(error, color = MaterialTheme.colorScheme.error)
        Button(onClick = { loading = true; scope.launch { when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl).login(username, password) }) { is ApiResult.Success -> onLogin(result.data); is ApiResult.Error -> { error = result.message; loading = false } } } }, enabled = !loading && username.isNotBlank() && password.isNotBlank()) { if (loading) CircularProgressIndicator() else Text(stringResource(R.string.login)) }
        Button(onClick = onChangeServer, enabled = !loading) { Text(stringResource(R.string.change_server)) }
    }
}
