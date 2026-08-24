package ru.wrtmonitor.app.ui.screens

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.res.stringResource
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.dto.WifiNetworkDto
import ru.wrtmonitor.app.ui.components.OptionSelector
import ru.wrtmonitor.app.ui.components.SecondaryActionButton
import ru.wrtmonitor.app.ui.components.SelectOption
import ru.wrtmonitor.app.ui.components.TonalActionButton

@Composable
internal fun WifiNetworkManagementRow(
    network: WifiNetworkDto,
    canShowQr: Boolean,
    canAssignProfile: Boolean,
    selectedProfile: String,
    profileOptions: List<SelectOption>,
    onShowQr: () -> Unit,
    onDelete: () -> Unit,
    onProfileSelected: (String) -> Unit,
    onApplyProfile: () -> Unit,
) {
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(network.ssid.ifBlank { network.id }, style = MaterialTheme.typography.titleSmall)
                Text(
                    listOf(
                        network.band,
                        network.network,
                        network.encryption,
                        stringResource(R.string.wifi_clients_count, network.stationCount),
                    ).filter(String::isNotBlank).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (canShowQr && network.enabled) {
                TonalActionButton(stringResource(R.string.wifi_show_qr), onShowQr)
            }
            SecondaryActionButton(stringResource(R.string.wifi_delete_network), onDelete)
        }
        if (canAssignProfile) {
            OptionSelector(
                stringResource(R.string.wifi_access_profile),
                selectedProfile,
                profileOptions,
                onProfileSelected,
            )
            Text(
                stringResource(R.string.wifi_access_profile_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            TonalActionButton(stringResource(R.string.apply), onApplyProfile)
        }
    }
}

@Composable
internal fun WifiAccessProfileConfirmationDialog(
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.wifi_access_profile)) },
        text = { Text(stringResource(R.string.wifi_access_profile_confirm)) },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) } },
        confirmButton = { TextButton(onClick = onConfirm) { Text(stringResource(R.string.apply)) } },
    )
}

@Composable
internal fun WifiQrDialog(networkName: String, bitmap: Bitmap, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(networkName) },
        text = {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Image(bitmap.asImageBitmap(), contentDescription = stringResource(R.string.wifi_show_qr), modifier = Modifier.fillMaxWidth())
                Text(stringResource(R.string.wifi_qr_private_hint), style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.close)) } },
    )
}
