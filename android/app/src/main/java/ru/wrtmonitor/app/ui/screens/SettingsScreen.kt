package ru.wrtmonitor.app.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
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
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.wrtmonitor.app.api.dto.JsonArray
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.WrtMonitorApi
import ru.wrtmonitor.app.api.SharedHttpClient
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
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private const val PROJECT_URL = "https://github.com/shurshick/wrtmonitor"
private const val RELEASES_URL = "https://api.github.com/repos/shurshick/wrtmonitor/releases?per_page=10"

internal sealed interface UpdateState {
    data class UpToDate(val latestVersion: String) : UpdateState
    data class Available(
        val latestVersion: String,
        val apkUrl: String?,
        val releasePageUrl: String,
    ) : UpdateState
    data object Error : UpdateState
}

@Composable
fun AppSettingsScreen(
    currentServerUrl: String,
    accessToken: String,
    isDarkTheme: Boolean,
    onThemeChange: (Boolean) -> Unit,
    onSave: (String) -> Unit,
    onLogout: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var serverUrl by remember(currentServerUrl) { mutableStateOf(currentServerUrl) }
    var serverUrlError by remember { mutableStateOf("") }
    var showAbout by remember { mutableStateOf(false) }
    var showSessions by remember { mutableStateOf(false) }
    var updateState by remember { mutableStateOf<UpdateState?>(null) }
    var checkingUpdate by remember { mutableStateOf(false) }
    var sessions by remember { mutableStateOf<List<WrtMonitorApi.UserSessionDto>>(emptyList()) }
    var currentPassword by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var accountMessage by remember { mutableStateOf("") }
    val api = remember(currentServerUrl, accessToken) { WrtMonitorApi(currentServerUrl, accessToken) }

    fun reloadAccount() {
        scope.launch {
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
            onDownloadUpdate = { version, url -> downloadAndInstallApk(context, version, url) },
            onOpenReleasePage = { openUrl(context, it) },
        )
        return
    }
    if (showSessions) {
        ActiveSessionsScreen(
            sessions = sessions,
            onRevoke = { sessionId ->
                scope.launch {
                    withContext(Dispatchers.IO) { api.revokeSession(sessionId) }
                    reloadAccount()
                }
            },
            onBack = { showSessions = false }
        )
        return
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        RouterPageHeader(
            title = stringResource(R.string.settings),
            subtitle = stringResource(R.string.settings_summary),
        )
        SectionCard(stringResource(R.string.appearance), subtitle = stringResource(R.string.appearance_summary)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(stringResource(R.string.dark_theme), style = MaterialTheme.typography.titleSmall)
                    Text(
                        stringResource(if (isDarkTheme) R.string.dark_theme_enabled else R.string.light_theme_enabled),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = isDarkTheme,
                    onCheckedChange = onThemeChange,
                )
            }
        }
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
            title = stringResource(R.string.active_sessions),
            subtitle = stringResource(R.string.active_sessions_summary),
        ) {
            SecondaryActionButton(stringResource(R.string.open), { showSessions = true }, Modifier.align(Alignment.End))
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
private fun AboutScreen(
    updateState: UpdateState?,
    checkingUpdate: Boolean,
    onBack: () -> Unit,
    onOpenProject: () -> Unit,
    onCheckUpdates: () -> Unit,
    onDownloadUpdate: (String, String) -> Unit,
    onOpenReleasePage: (String) -> Unit,
) {
    BackHandler(onBack = onBack)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.navigate_back))
            }
            Text(
                stringResource(R.string.about_app),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
        }
        SectionCard(
            title = stringResource(R.string.app_name),
            subtitle = stringResource(R.string.app_tagline),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Image(
                    painter = painterResource(R.drawable.ic_launcher_foreground),
                    contentDescription = null,
                    modifier = Modifier.size(52.dp),
                )
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        stringResource(R.string.app_version_value, appVersionName(LocalContext.current)),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        stringResource(R.string.copyright_owner),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Text(
                stringResource(R.string.app_description),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            SecondaryActionButton(stringResource(R.string.project_page), onOpenProject)
        }
        SectionCard(
            title = stringResource(R.string.updates),
            subtitle = stringResource(R.string.update_check_hint),
        ) {
            when (val state = updateState) {
                null -> InfoRow(
                    stringResource(R.string.app_version),
                    appVersionName(LocalContext.current),
                )
                is UpdateState.UpToDate -> Text(stringResource(R.string.app_up_to_date, state.latestVersion))
                is UpdateState.Available -> {
                    Text(
                        stringResource(R.string.update_available, state.latestVersion),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        stringResource(R.string.update_install_hint),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    ActionRow {
                        state.apkUrl?.let { apkUrl ->
                            PrimaryActionButton(
                                stringResource(R.string.download_update),
                                { onDownloadUpdate(state.latestVersion, apkUrl) },
                            )
                        }
                        SecondaryActionButton(
                            stringResource(R.string.open_release_page),
                            { onOpenReleasePage(state.releasePageUrl) },
                        )
                    }
                }
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
    val (status, response) = SharedHttpClient.request(
        RELEASES_URL,
        headers = mapOf(
            "Accept" to "application/vnd.github+json",
            "User-Agent" to "wrtmonitor-android",
        ),
    )
    if (status !in 200..299) throw IllegalStateException("HTTP $status")
    return resolveUpdateState(currentVersion, response)
}

internal fun resolveUpdateState(currentVersion: String, response: String): UpdateState {
    val releases = JsonArray(response)
    val release = (0 until releases.length()).mapNotNull { releases.optJsonObject(it) }.firstOrNull { !it.optBoolean("draft", false) } ?: throw IllegalStateException("No published releases")
    val latestVersion = release.optString("tag_name").removePrefix("v")
    val assets = release.optJsonArray("assets")
    var apkUrl: String? = null
    if (assets != null) {
        for (i in 0 until assets.length()) {
            val asset = assets.optJsonObject(i)
            if (asset?.optString("name")?.endsWith(".apk") == true) {
                apkUrl = asset.optString("browser_download_url")
                break
            }
        }
    }
    return if (VersionComparator.compare(latestVersion, currentVersion) > 0) {
        UpdateState.Available(
            latestVersion = latestVersion,
            apkUrl = apkUrl?.takeIf(String::isNotBlank),
            releasePageUrl = release.optString("html_url"),
        )
    } else {
        UpdateState.UpToDate(latestVersion)
    }
}

private fun downloadAndInstallApk(context: android.content.Context, version: String, url: String) {
    val safeVersion = version.replace(Regex("[^A-Za-z0-9._-]"), "-")
    val request = android.app.DownloadManager.Request(Uri.parse(url)).apply {
        setMimeType("application/vnd.android.package-archive")
        setTitle(context.getString(R.string.update_download_title, version))
        setDestinationInExternalFilesDir(
            context,
            android.os.Environment.DIRECTORY_DOWNLOADS,
            "wrtmonitor-$safeVersion-${System.currentTimeMillis()}.apk",
        )
        setNotificationVisibility(android.app.DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
    }
    val downloadManager = context.getSystemService(android.content.Context.DOWNLOAD_SERVICE) as android.app.DownloadManager
    val downloadId = downloadManager.enqueue(request)

    val receiver = object : android.content.BroadcastReceiver() {
        override fun onReceive(ctx: android.content.Context, intent: Intent) {
            val id = intent.getLongExtra(android.app.DownloadManager.EXTRA_DOWNLOAD_ID, -1)
            if (id == downloadId) {
                val uri = downloadManager.getUriForDownloadedFile(downloadId)
                if (uri != null) {
                    val installIntent = Intent(Intent.ACTION_VIEW).apply {
                        setDataAndType(uri, "application/vnd.android.package-archive")
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION
                    }
                    ctx.startActivity(installIntent)
                }
                ctx.unregisterReceiver(this)
            }
        }
    }
    androidx.core.content.ContextCompat.registerReceiver(
        context,
        receiver,
        android.content.IntentFilter(android.app.DownloadManager.ACTION_DOWNLOAD_COMPLETE),
        androidx.core.content.ContextCompat.RECEIVER_EXPORTED
    )
}

@Composable
private fun ActiveSessionsScreen(
    sessions: List<WrtMonitorApi.UserSessionDto>,
    onRevoke: (String) -> Unit,
    onBack: () -> Unit
) {
    BackHandler(onBack = onBack)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) }
            Text(stringResource(R.string.active_sessions), style = MaterialTheme.typography.titleLarge)
        }
        
        sessions.filterNot { it.revoked }.forEach { session ->
            SectionCard(session.clientName) {
                val sessionType = if (session.clientType == "mobile_pairing") {
                    stringResource(R.string.session_type_qr)
                } else {
                    stringResource(R.string.session_type_password)
                }
                InfoRow(
                    sessionType,
                    listOfNotNull(
                        session.ipAddress.ifBlank { null },
                        formatSessionTimestamp(session.lastUsedAt)
                            ?: formatSessionTimestamp(session.createdAt),
                    ).joinToString(" · "),
                )
                SecondaryActionButton(
                    label = stringResource(R.string.revoke_session),
                    onClick = { onRevoke(session.id) },
                    modifier = Modifier.align(Alignment.End)
                )
            }
        }
    }
}
