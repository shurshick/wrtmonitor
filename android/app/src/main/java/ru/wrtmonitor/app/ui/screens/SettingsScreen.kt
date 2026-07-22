package ru.wrtmonitor.app.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.domain.VersionComparator
import ru.wrtmonitor.app.pairing.MobilePairingPayloadException
import ru.wrtmonitor.app.pairing.normalizePairingServerUrl
import ru.wrtmonitor.app.ui.components.InfoRow
import ru.wrtmonitor.app.ui.components.ActionRow
import ru.wrtmonitor.app.ui.components.MessageBanner
import ru.wrtmonitor.app.ui.components.PrimaryActionButton
import ru.wrtmonitor.app.ui.components.RouterPageHeader
import ru.wrtmonitor.app.ui.components.SecondaryActionButton
import ru.wrtmonitor.app.ui.components.SectionCard
import ru.wrtmonitor.app.ui.components.TonalActionButton
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private const val PROJECT_URL = "https://github.com/shurshick/wrtmonitor"
private const val RELEASES_URL = "https://api.github.com/repos/shurshick/wrtmonitor/releases?per_page=10"

private sealed interface UpdateState {
    data class UpToDate(val latestVersion: String) : UpdateState
    data class Available(val latestVersion: String, val releaseUrl: String) : UpdateState
    data object Error : UpdateState
}

@Composable
fun AppSettingsScreen(
    currentServerUrl: String,
    accessToken: String,
    onSave: (String) -> Unit,
    onLogout: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var serverUrl by remember(currentServerUrl) { mutableStateOf(currentServerUrl) }
    var serverUrlError by remember { mutableStateOf("") }
    var showAbout by remember { mutableStateOf(false) }
    var updateState by remember { mutableStateOf<UpdateState?>(null) }
    var checkingUpdate by remember { mutableStateOf(false) }
    var notifications by remember { mutableStateOf<List<WrtMonitorApi.OperationNotificationDto>>(emptyList()) }
    var sessions by remember { mutableStateOf<List<WrtMonitorApi.UserSessionDto>>(emptyList()) }
    var currentPassword by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var accountMessage by remember { mutableStateOf("") }
    val api = remember(currentServerUrl, accessToken) { WrtMonitorApi(currentServerUrl, accessToken) }

    fun reloadAccount() {
        scope.launch {
            when (val result = withContext(Dispatchers.IO) { api.getOperationNotifications() }) {
                is ApiResult.Success -> notifications = result.data
                is ApiResult.Error -> accountMessage = result.message
            }
            when (val result = withContext(Dispatchers.IO) { api.getSessions() }) {
                is ApiResult.Success -> sessions = result.data
                is ApiResult.Error -> accountMessage = result.message
            }
        }
    }

    LaunchedEffect(api) { reloadAccount() }
    if (showAbout) {
        AboutScreen(
            updateState = updateState,
            checkingUpdate = checkingUpdate,
            onBack = { showAbout = false },
            onOpenProject = { openUrl(context, PROJECT_URL) },
            onCheckUpdates = {
                checkingUpdate = true
                updateState = null
                scope.launch {
                    updateState = runCatching { withContext(Dispatchers.IO) { checkForUpdate(appVersionName(context)) } }.getOrElse { UpdateState.Error }
                    checkingUpdate = false
                }
            },
            onOpenRelease = { openUrl(context, it) }
        )
        return
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        RouterPageHeader(
            title = stringResource(R.string.settings),
            subtitle = stringResource(R.string.settings_summary),
        )
        SectionCard(stringResource(R.string.server_connection), subtitle = currentServerUrl) {
            OutlinedTextField(serverUrl, { serverUrl = it }, label = { Text(stringResource(R.string.server_url)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            MessageBanner(serverUrlError, error = true)
            ActionRow {
                PrimaryActionButton(stringResource(R.string.save), {
                    try {
                        onSave(normalizePairingServerUrl(serverUrl))
                        serverUrlError = ""
                    } catch (_: MobilePairingPayloadException) {
                        serverUrlError = context.getString(R.string.server_url_invalid)
                    }
                })
                SecondaryActionButton(stringResource(R.string.logout), onLogout)
            }
        }
        SectionCard(
            title = stringResource(R.string.server_notifications),
            subtitle = stringResource(R.string.server_notifications_summary),
        ) {
            if (notifications.isEmpty()) {
                Text(stringResource(R.string.no_server_notifications), color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                notifications.forEach { item ->
                    Text(item.title, style = MaterialTheme.typography.titleSmall)
                    Text(item.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        SectionCard(
            title = stringResource(R.string.active_sessions),
            subtitle = stringResource(R.string.active_sessions_summary),
        ) {
            sessions.filterNot { it.revoked }.forEach { session ->
                val sessionType = if (session.clientType == "mobile_pairing") {
                    stringResource(R.string.session_type_qr)
                } else {
                    stringResource(R.string.session_type_password)
                }
                InfoRow(
                    session.clientName,
                    listOfNotNull(
                        sessionType,
                        session.ipAddress.ifBlank { null },
                        formatSessionTimestamp(session.lastUsedAt)
                            ?: formatSessionTimestamp(session.createdAt),
                    ).joinToString(" · "),
                )
                SecondaryActionButton(stringResource(R.string.revoke_session), {
                    scope.launch {
                        withContext(Dispatchers.IO) { api.revokeSession(session.id) }
                        reloadAccount()
                    }
                }, Modifier.align(Alignment.End))
            }
        }
        SectionCard(
            title = stringResource(R.string.change_owner_password),
            subtitle = stringResource(R.string.change_owner_password_summary),
        ) {
            OutlinedTextField(
                currentPassword,
                { currentPassword = it },
                label = { Text(stringResource(R.string.current_password)) },
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            OutlinedTextField(
                newPassword,
                { newPassword = it },
                label = { Text(stringResource(R.string.new_password)) },
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            if (accountMessage.isNotBlank()) Text(accountMessage, style = MaterialTheme.typography.bodySmall)
            PrimaryActionButton(stringResource(R.string.change_password), {
                scope.launch {
                    val successMessage = context.getString(R.string.password_changed_login_again)
                    accountMessage = when (val result = withContext(Dispatchers.IO) {
                        api.changePassword(currentPassword, newPassword)
                    }) {
                        is ApiResult.Success -> successMessage
                        is ApiResult.Error -> result.message
                    }
                    if (accountMessage == successMessage) onLogout()
                }
            }, Modifier.align(Alignment.End))
        }
        SectionCard(
            title = stringResource(R.string.about_app),
            subtitle = stringResource(R.string.about_app_summary),
        ) {
            SecondaryActionButton(stringResource(R.string.open), { showAbout = true }, Modifier.align(Alignment.End))
        }
    }
}

private fun formatSessionTimestamp(value: String): String? = runCatching {
    Instant.parse(value).atZone(ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
}.getOrNull()

@Composable
private fun AboutScreen(updateState: UpdateState?, checkingUpdate: Boolean, onBack: () -> Unit, onOpenProject: () -> Unit, onCheckUpdates: () -> Unit, onOpenRelease: (String) -> Unit) {
    BackHandler(onBack = onBack)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) }
            Text(stringResource(R.string.about_app), style = MaterialTheme.typography.titleLarge)
        }
        SectionCard(stringResource(R.string.app_name)) {
            InfoRow(stringResource(R.string.app_version), appVersionName(LocalContext.current))
            Text(stringResource(R.string.copyright), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SecondaryActionButton(stringResource(R.string.project_page), onOpenProject, Modifier.align(Alignment.End))
        }
        SectionCard(stringResource(R.string.updates)) {
            when (val state = updateState) {
                null -> Text(stringResource(R.string.update_check_hint), color = MaterialTheme.colorScheme.onSurfaceVariant)
                is UpdateState.UpToDate -> Text(stringResource(R.string.app_up_to_date, state.latestVersion))
                is UpdateState.Available -> { Text(stringResource(R.string.update_available, state.latestVersion)); PrimaryActionButton(stringResource(R.string.download_update), { onOpenRelease(state.releaseUrl) }, Modifier.align(Alignment.End)) }
                UpdateState.Error -> Text(stringResource(R.string.update_check_error), color = MaterialTheme.colorScheme.error)
            }
            TonalActionButton(
                label = stringResource(R.string.check_updates),
                onClick = onCheckUpdates,
                enabled = !checkingUpdate,
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
}

private fun appVersionName(context: android.content.Context): String = context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: ""
private fun openUrl(context: android.content.Context, url: String) = context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
private fun checkForUpdate(currentVersion: String): UpdateState {
    val connection = (URL(RELEASES_URL).openConnection() as HttpURLConnection).apply { requestMethod = "GET"; connectTimeout = 10_000; readTimeout = 10_000; setRequestProperty("Accept", "application/vnd.github+json"); setRequestProperty("User-Agent", "wrtmonitor-android") }
    val status = connection.responseCode
    if (status !in 200..299) throw IllegalStateException("HTTP $status")
    val releases = JSONArray(connection.inputStream.bufferedReader().use { it.readText() })
    val release = (0 until releases.length()).mapNotNull { releases.optJSONObject(it) }.firstOrNull { !it.optBoolean("draft", false) } ?: throw IllegalStateException("No published releases")
    val latestVersion = release.optString("tag_name").removePrefix("v")
    return if (VersionComparator.compare(latestVersion, currentVersion) > 0) UpdateState.Available(latestVersion, release.optString("html_url")) else UpdateState.UpToDate(latestVersion)
}
