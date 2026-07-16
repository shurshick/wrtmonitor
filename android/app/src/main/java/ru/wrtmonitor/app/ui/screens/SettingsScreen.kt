package ru.wrtmonitor.app.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.domain.VersionComparator
import ru.wrtmonitor.app.ui.components.InfoRow
import java.net.HttpURLConnection
import java.net.URL

private const val PROJECT_URL = "https://github.com/shurshick/wrtmonitor"
private const val RELEASES_URL = "https://api.github.com/repos/shurshick/wrtmonitor/releases?per_page=10"

private sealed interface UpdateState {
    data class UpToDate(val latestVersion: String) : UpdateState
    data class Available(val latestVersion: String, val releaseUrl: String) : UpdateState
    data object Error : UpdateState
}

@Composable
fun AppSettingsScreen(currentServerUrl: String, onSave: (String) -> Unit, onLogout: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var serverUrl by remember(currentServerUrl) { mutableStateOf(currentServerUrl) }
    var showAbout by remember { mutableStateOf(false) }
    var updateState by remember { mutableStateOf<UpdateState?>(null) }
    var checkingUpdate by remember { mutableStateOf(false) }
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
        Text(stringResource(R.string.settings), style = MaterialTheme.typography.titleLarge)
        OutlinedTextField(serverUrl, { serverUrl = it }, label = { Text(stringResource(R.string.server_url)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        Button({ onSave(serverUrl) }) { Text(stringResource(R.string.save)) }
        TextButton(onLogout) { Text(stringResource(R.string.logout)) }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.about_app), style = MaterialTheme.typography.titleMedium)
                Text(stringResource(R.string.about_app_summary), color = MaterialTheme.colorScheme.onSurfaceVariant)
                Button({ showAbout = true }, modifier = Modifier.align(Alignment.End)) { Text(stringResource(R.string.open)) }
            }
        }
    }
}

@Composable
private fun AboutScreen(updateState: UpdateState?, checkingUpdate: Boolean, onBack: () -> Unit, onOpenProject: () -> Unit, onCheckUpdates: () -> Unit, onOpenRelease: (String) -> Unit) {
    BackHandler(onBack = onBack)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) }
            Text(stringResource(R.string.about_app), style = MaterialTheme.typography.titleLarge)
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.app_name), style = MaterialTheme.typography.titleLarge)
                InfoRow(stringResource(R.string.app_version), appVersionName(LocalContext.current))
                Text(stringResource(R.string.copyright), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Button(onOpenProject, modifier = Modifier.align(Alignment.End)) { Text(stringResource(R.string.project_page)) }
            }
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.updates), style = MaterialTheme.typography.titleMedium)
                when (val state = updateState) {
                    null -> Text(stringResource(R.string.update_check_hint), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    is UpdateState.UpToDate -> Text(stringResource(R.string.app_up_to_date, state.latestVersion))
                    is UpdateState.Available -> { Text(stringResource(R.string.update_available, state.latestVersion)); Button({ onOpenRelease(state.releaseUrl) }, modifier = Modifier.align(Alignment.End)) { Text(stringResource(R.string.download_update)) } }
                    UpdateState.Error -> Text(stringResource(R.string.update_check_error), color = MaterialTheme.colorScheme.error)
                }
                Button(onCheckUpdates, enabled = !checkingUpdate, modifier = Modifier.align(Alignment.End)) {
                    if (checkingUpdate) CircularProgressIndicator(modifier = Modifier.widthIn(max = 20.dp), strokeWidth = 2.dp) else Text(stringResource(R.string.check_updates))
                }
            }
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
