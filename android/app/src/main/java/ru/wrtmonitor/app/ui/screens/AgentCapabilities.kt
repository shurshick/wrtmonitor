package ru.wrtmonitor.app.ui.screens

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import ru.wrtmonitor.app.R

private val capabilityGroups = linkedMapOf(
    R.string.capability_group_agent to listOf("agent."),
    R.string.capability_group_telemetry to listOf("telemetry."),
    R.string.capability_group_wifi to listOf("wifi."),
    R.string.capability_group_network to listOf("network."),
    R.string.capability_group_clients to listOf("clients.", "dhcp."),
    R.string.capability_group_diagnostics to listOf("diagnostics."),
    R.string.capability_group_system to listOf("system."),
)

@Composable
internal fun capabilitiesSummary(capabilities: Map<String, Boolean>): String {
    if (capabilities.isEmpty()) return stringResource(R.string.no_data)
    val enabled = capabilities.count { it.value }
    val disabled = capabilities.size - enabled
    return stringResource(R.string.capabilities_summary, enabled, disabled)
}

@Composable
internal fun groupedCapabilities(
    capabilities: Map<String, Boolean>,
): List<Pair<String, List<String>>> {
    if (capabilities.isEmpty()) return emptyList()
    val remaining = capabilities.toSortedMap().toMutableMap()
    val result = mutableListOf<Pair<String, List<String>>>()

    capabilityGroups.forEach { (titleRes, prefixes) ->
        val items = remaining.keys.filter { key ->
            prefixes.any { prefix -> key.startsWith(prefix) }
        }
        if (items.isNotEmpty()) {
            result += stringResource(titleRes) to items
            items.forEach { remaining.remove(it) }
        }
    }

    if (remaining.isNotEmpty()) {
        result += stringResource(R.string.capability_group_other) to remaining.keys.toList()
    }

    return result
}
