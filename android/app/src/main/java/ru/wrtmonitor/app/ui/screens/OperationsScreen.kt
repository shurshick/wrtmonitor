package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material3.AssistChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.dto.AutomationRuleDto
import ru.wrtmonitor.app.api.dto.EventDto
import ru.wrtmonitor.app.api.dto.NotificationRuleDto
import ru.wrtmonitor.app.data.RouterRepository
import ru.wrtmonitor.app.ui.components.ActionRow
import ru.wrtmonitor.app.ui.components.DangerActionButton
import ru.wrtmonitor.app.ui.components.ExpandableSettingsCard
import ru.wrtmonitor.app.ui.components.MessageBanner
import ru.wrtmonitor.app.ui.components.PrimaryActionButton
import ru.wrtmonitor.app.ui.components.RouterPageHeader
import ru.wrtmonitor.app.ui.components.SecondaryActionButton
import ru.wrtmonitor.app.ui.components.SectionCard
import ru.wrtmonitor.app.ui.components.StatusPill
import ru.wrtmonitor.app.viewmodel.OperationsViewModel
import ru.wrtmonitor.app.viewmodel.RouterViewModelFactory
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

@Composable
fun OperationsScreen(
    serverUrl: String,
    accessToken: String,
    deviceId: String,
    onSessionExpired: () -> Unit,
) {
    val viewModel: OperationsViewModel = viewModel(
        key = "operations:$serverUrl:$deviceId",
        factory = RouterViewModelFactory { OperationsViewModel(RouterRepository(serverUrl, accessToken), deviceId) },
    )
    val state = viewModel.state
    var filter by rememberSaveable { mutableStateOf("open") }

    LaunchedEffect(Unit) { viewModel.refresh() }
    LaunchedEffect(state.sessionExpired) { if (state.sessionExpired) onSessionExpired() }

    RouterPageHeader(
        title = stringResource(R.string.events_and_automation),
        subtitle = stringResource(R.string.events_summary),
        refreshing = state.loading,
        onRefresh = viewModel::refresh,
    )
    state.error?.let { MessageBanner(it, error = true) }

    ActionRow {
        listOf("open", "critical", "all").forEach { value ->
            AssistChip(
                onClick = { filter = value },
                label = { Text(eventFilterLabel(value)) },
                leadingIcon = if (filter == value) ({ Text("•") }) else null,
            )
        }
    }

    val visibleEvents = state.events.filter {
        when (filter) {
            "open" -> it.status == "open"
            "critical" -> it.severity == "critical"
            else -> true
        }
    }
    SectionCard(
        title = stringResource(R.string.event_log),
        subtitle = stringResource(R.string.event_log_count, visibleEvents.size),
    ) {
        if (visibleEvents.isEmpty()) {
            Text(stringResource(R.string.no_events), color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            visibleEvents.take(40).forEachIndexed { index, event ->
                EventRow(event, viewModel::acknowledge, viewModel::snooze)
                if (index != visibleEvents.take(40).lastIndex) HorizontalDivider()
            }
        }
    }

    ExpandableSettingsCard(
        title = stringResource(R.string.notification_rules),
        summary = stringResource(R.string.notification_rules_summary, state.notificationRules.size),
    ) {
        state.notificationRules.filter { it.deviceId == null || it.deviceId == deviceId }.forEach { rule ->
            NotificationRuleRow(rule, viewModel::deleteNotification)
        }
        var name by rememberSaveable { mutableStateOf("") }
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            label = { Text(stringResource(R.string.notification_rule_name)) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        PrimaryActionButton(
            label = stringResource(R.string.create_notification_rule),
            enabled = name.isNotBlank(),
            onClick = { viewModel.addInAppRule(name.trim()); name = "" },
        )
    }

    ExpandableSettingsCard(
        title = stringResource(R.string.automation),
        summary = stringResource(R.string.automation_summary, state.automationRules.size),
    ) {
        state.automationRules.filter { it.deviceId == null || it.deviceId == deviceId }.forEach { rule ->
            AutomationRuleRow(rule, viewModel::toggleAutomation, viewModel::deleteAutomation)
        }
        if (state.templates.isNotEmpty()) {
            Text(stringResource(R.string.safe_templates), style = MaterialTheme.typography.titleSmall)
            state.templates.forEach { template ->
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(template.name, fontWeight = FontWeight.SemiBold)
                        Text(
                            "${template.triggerType} → ${template.actionCommand}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    PrimaryActionButton(stringResource(R.string.add_rule), { viewModel.addAutomation(template) })
                }
            }
        }
    }

    ExpandableSettingsCard(
        title = stringResource(R.string.automation_history),
        summary = stringResource(R.string.automation_runs_count, state.runs.size),
    ) {
        if (state.runs.isEmpty()) Text(stringResource(R.string.no_automation_runs))
        state.runs.take(20).forEach { run ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusPill(run.status.uppercase(), run.status in setOf("queued", "dry_run"))
                Column(Modifier.weight(1f)) {
                    Text(run.message.ifBlank { run.status })
                    Text(formatOperationTime(run.createdAt), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun EventRow(event: EventDto, acknowledge: (EventDto) -> Unit, snooze: (EventDto) -> Unit) {
    val accent = when (event.severity) {
        "critical" -> MaterialTheme.colorScheme.error
        "warning" -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.primary
    }
    Surface(color = Color.Transparent) {
        Column(Modifier.padding(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(event.title, Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                StatusPill(event.severity.uppercase(), event.severity == "info")
            }
            if (event.message.isNotBlank()) Text(event.message, style = MaterialTheme.typography.bodySmall)
            Text(
                "${event.eventType} · ${formatOperationTime(event.lastOccurredAt)}${if (event.occurrenceCount > 1) " · ×${event.occurrenceCount}" else ""}",
                style = MaterialTheme.typography.labelSmall,
                color = accent,
            )
            if (event.status == "open") {
                ActionRow {
                    SecondaryActionButton(stringResource(R.string.acknowledge), { acknowledge(event) })
                    SecondaryActionButton(stringResource(R.string.snooze_one_hour), { snooze(event) })
                }
            }
        }
    }
}

@Composable
private fun NotificationRuleRow(rule: NotificationRuleDto, delete: (NotificationRuleDto) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Notifications, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
        Column(Modifier.weight(1f)) {
            Text(rule.name, fontWeight = FontWeight.SemiBold)
            Text(rule.channelTypes.joinToString(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        DangerActionButton(stringResource(R.string.delete), { delete(rule) })
    }
}

@Composable
private fun AutomationRuleRow(rule: AutomationRuleDto, toggle: (AutomationRuleDto) -> Unit, delete: (AutomationRuleDto) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Bolt, contentDescription = null, tint = MaterialTheme.colorScheme.tertiary)
        Column(Modifier.weight(1f)) {
            Text(rule.name, fontWeight = FontWeight.SemiBold)
            Text("${rule.triggerType} → ${rule.actionCommand}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = rule.enabled, onCheckedChange = { toggle(rule) })
        DangerActionButton(stringResource(R.string.delete), { delete(rule) })
    }
}

@Composable
private fun eventFilterLabel(value: String) = when (value) {
    "open" -> stringResource(R.string.open_events)
    "critical" -> stringResource(R.string.critical_events)
    else -> stringResource(R.string.all_events)
}

private fun formatOperationTime(value: String?): String = runCatching {
    OffsetDateTime.parse(value).format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
}.getOrDefault(value.orEmpty())
