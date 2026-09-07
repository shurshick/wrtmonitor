package ru.wrtmonitor.app.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.HourglassEmpty
import androidx.compose.material.icons.filled.Inbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.ui.theme.WrtSizes
import ru.wrtmonitor.app.ui.theme.WrtSpacing

@Composable
fun WrtLoadingState(message: String = stringResource(R.string.loading_data)) {
    StatePanel(Icons.Default.HourglassEmpty, message, progress = true)
}

@Composable
fun WrtEmptyState(message: String = stringResource(R.string.no_data)) {
    StatePanel(Icons.Default.Inbox, message)
}

@Composable
fun WrtErrorState(message: String, onRetry: (() -> Unit)? = null) {
    StatePanel(Icons.Default.ErrorOutline, stringResource(R.string.load_error), message, onRetry = onRetry, error = true)
}

@Composable
fun WrtOfflineState(message: String, onRetry: (() -> Unit)? = null) {
    StatePanel(Icons.Default.CloudOff, stringResource(R.string.router_unavailable), message, onRetry = onRetry)
}

@Composable
private fun StatePanel(
    icon: ImageVector,
    title: String,
    detail: String? = null,
    progress: Boolean = false,
    onRetry: (() -> Unit)? = null,
    error: Boolean = false,
) {
    val accent = if (error) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        shape = MaterialTheme.shapes.medium,
    ) {
        Column(
            modifier = Modifier.padding(WrtSpacing.lg),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(WrtSpacing.sm),
        ) {
            if (progress) CircularProgressIndicator(Modifier.size(WrtSizes.iconLarge), strokeWidth = WrtSpacing.xxs)
            else Icon(icon, contentDescription = null, tint = accent, modifier = Modifier.size(WrtSizes.iconLarge))
            Text(title, style = MaterialTheme.typography.titleMedium)
            detail?.takeIf(String::isNotBlank)?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            onRetry?.let { SecondaryActionButton(stringResource(R.string.refresh), it) }
        }
    }
}
