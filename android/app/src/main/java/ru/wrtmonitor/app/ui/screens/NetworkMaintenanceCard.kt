package ru.wrtmonitor.app.ui.screens

import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.ui.components.ExpandableSettingsCard
import ru.wrtmonitor.app.ui.components.OptionSelector
import ru.wrtmonitor.app.ui.components.SecondaryActionButton
import ru.wrtmonitor.app.ui.components.SelectOption

@Composable
internal fun NetworkMaintenanceCard(
    capabilities: Map<String, Boolean>,
    interfaceName: String,
    interfaceOptions: List<SelectOption>,
    onInterfaceChange: (String) -> Unit,
    onCommand: (PendingSafeCommand) -> Unit,
) {
    if (capabilities["network.interface_restart"] != true && capabilities["network.restart"] != true) return
    val interfaceRestartQueued = stringResource(R.string.interface_restart_queued)
    val networkRestartQueued = stringResource(R.string.network_restart_queued)
    ExpandableSettingsCard(stringResource(R.string.network_maintenance), stringResource(R.string.network_maintenance_summary)) {
        if (capabilities["network.interface_restart"] == true) {
            OptionSelector(stringResource(R.string.network_interfaces), interfaceName, interfaceOptions, onInterfaceChange)
            SecondaryActionButton(
                label = stringResource(R.string.restart_interface),
                onClick = {
                    onCommand(
                        PendingSafeCommand(
                            "network.interface_restart",
                            JsonObject().put("interface", interfaceName),
                            interfaceRestartQueued,
                        ),
                    )
                },
                enabled = interfaceName.isNotBlank(),
                modifier = Modifier.align(Alignment.End),
            )
        }
        if (capabilities["network.restart"] == true) {
            SecondaryActionButton(
                stringResource(R.string.restart_network),
                { onCommand(PendingSafeCommand("network.restart", JsonObject(), networkRestartQueued)) },
                Modifier.align(Alignment.End),
            )
        }
    }
}
