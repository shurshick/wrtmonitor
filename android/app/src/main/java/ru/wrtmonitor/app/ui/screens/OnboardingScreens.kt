package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.Image
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.res.painterResource
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
import ru.wrtmonitor.app.ui.components.MessageBanner
import ru.wrtmonitor.app.ui.components.PrimaryActionButton
import ru.wrtmonitor.app.ui.components.SecondaryActionButton
import ru.wrtmonitor.app.ui.components.SectionCard
import ru.wrtmonitor.app.pairing.MobilePairingSetup

@Composable
fun ServerSetupScreen(
    onSave: (String) -> Unit,
    onScanQr: () -> Unit,
    pairingError: String = "",
) {
    var serverUrl by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        OnboardingHeader()
        SectionCard(
            title = stringResource(R.string.server_connection),
            subtitle = stringResource(R.string.first_run_server_prompt),
        ) {
            SecondaryActionButton(
                label = stringResource(R.string.scan_pairing_qr),
                onClick = onScanQr,
                modifier = Modifier.align(Alignment.End),
            )
            Text(
                stringResource(R.string.or_enter_server_manually),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(serverUrl, { serverUrl = it }, label = { Text(stringResource(R.string.server_url)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            MessageBanner(pairingError, error = true)
            PrimaryActionButton(
                label = stringResource(R.string.save),
                onClick = { onSave(serverUrl) },
                enabled = serverUrl.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
}

@Composable
fun PairingConfirmationScreen(
    setup: MobilePairingSetup,
    onConnected: (WrtMonitorApi.PairingResult) -> Unit,
    onCancel: () -> Unit,
) {
    var error by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val pairingMessages = mapOf(
        "pairing_used" to stringResource(R.string.pairing_used),
        "pairing_expired" to stringResource(R.string.pairing_expired),
        "pairing_revoked" to stringResource(R.string.pairing_revoked),
        "pairing_rate_limited" to stringResource(R.string.pairing_rate_limited),
        "pairing_server_changed" to stringResource(R.string.pairing_server_changed),
        "pairing_invalid" to stringResource(R.string.pairing_qr_invalid),
    )
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        OnboardingHeader()
        SectionCard(
            title = stringResource(R.string.confirm_server_connection),
            subtitle = stringResource(R.string.confirm_server_connection_hint),
        ) {
            Text(setup.serverUrl, style = MaterialTheme.typography.titleMedium)
            MessageBanner(
                stringResource(if (setup.secure) R.string.secure_connection else R.string.local_http_warning),
                error = !setup.secure,
            )
            MessageBanner(error, error = true)
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                SecondaryActionButton(
                    label = stringResource(R.string.cancel),
                    onClick = onCancel,
                    enabled = !loading,
                )
                PrimaryActionButton(
                    label = stringResource(R.string.connect),
                    onClick = {
                        loading = true
                        scope.launch {
                            when (val result = withContext(Dispatchers.IO) {
                                WrtMonitorApi(setup.serverUrl).exchangeMobilePairing(
                                    setup.pairingToken,
                                    "WrtMonitor Android",
                                )
                            }) {
                                is ApiResult.Success -> onConnected(result.data)
                                is ApiResult.Error -> {
                                    error = pairingMessages[result.code] ?: result.message
                                    loading = false
                                }
                            }
                        }
                    },
                    enabled = !loading,
                    loading = loading,
                )
            }
        }
    }
}

@Composable
fun AdminLoginScreen(serverUrl: String, onLogin: (WrtMonitorApi.AuthTokens) -> Unit, onChangeServer: () -> Unit) {
    var username by remember { mutableStateOf("") }; var password by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }; var loading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        OnboardingHeader()
        SectionCard(stringResource(R.string.login), subtitle = serverUrl) {
            OutlinedTextField(username, { username = it }, label = { Text(stringResource(R.string.admin_label)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(password, { password = it }, label = { Text(stringResource(R.string.password_label)) }, modifier = Modifier.fillMaxWidth(), visualTransformation = PasswordVisualTransformation(), singleLine = true)
            MessageBanner(error, error = true)
            PrimaryActionButton(
                label = stringResource(R.string.login),
                onClick = { loading = true; scope.launch { when (val result = withContext(Dispatchers.IO) { WrtMonitorApi(serverUrl).login(username, password) }) { is ApiResult.Success -> onLogin(result.data); is ApiResult.Error -> { error = result.message; loading = false } } } },
                enabled = !loading && username.isNotBlank() && password.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
                loading = loading,
            )
            SecondaryActionButton(
                label = stringResource(R.string.change_server),
                onClick = onChangeServer,
                enabled = !loading,
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
}

@Composable
private fun OnboardingHeader() {
    Column(
        Modifier.fillMaxWidth().padding(bottom = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Image(painterResource(R.drawable.ic_launcher_foreground), null, Modifier.size(72.dp))
        Text(stringResource(R.string.app_name), style = MaterialTheme.typography.headlineMedium)
        Text(
            stringResource(R.string.app_tagline),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
