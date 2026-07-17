package ru.wrtmonitor.app.ui.screens

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.VpnKey
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.ui.components.DestinationRow
import ru.wrtmonitor.app.ui.components.RouterPageHeader
import ru.wrtmonitor.app.ui.components.SectionCard

@Composable
fun RouterSectionsScreen(
    onOpenRules: () -> Unit,
    onOpenVpn: () -> Unit,
    onOpenSystem: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    RouterPageHeader(
        title = stringResource(R.string.more),
        subtitle = stringResource(R.string.more_summary),
    )
    SectionCard(stringResource(R.string.security_and_connections)) {
        DestinationRow(
            icon = Icons.Default.Security,
            title = stringResource(R.string.network_rules),
            value = "",
            detail = stringResource(R.string.network_rules_summary),
            onClick = onOpenRules,
        )
        HorizontalDivider()
        DestinationRow(
            icon = Icons.Default.VpnKey,
            title = stringResource(R.string.vpn_title),
            value = "",
            detail = stringResource(R.string.vpn_summary),
            accent = MaterialTheme.colorScheme.secondary,
            onClick = onOpenVpn,
        )
    }
    SectionCard(stringResource(R.string.management)) {
        DestinationRow(
            icon = Icons.Default.Build,
            title = stringResource(R.string.system_and_maintenance),
            value = "",
            detail = stringResource(R.string.system_and_maintenance_summary),
            accent = MaterialTheme.colorScheme.tertiary,
            onClick = onOpenSystem,
        )
        HorizontalDivider()
        DestinationRow(
            icon = Icons.Default.Settings,
            title = stringResource(R.string.app_and_server),
            value = "",
            detail = stringResource(R.string.app_and_server_summary),
            onClick = onOpenSettings,
        )
    }
}
