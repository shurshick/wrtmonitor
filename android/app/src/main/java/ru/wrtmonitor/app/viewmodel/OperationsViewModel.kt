package ru.wrtmonitor.app.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import ru.wrtmonitor.app.api.ApiResult
import ru.wrtmonitor.app.api.dto.AutomationRuleDto
import ru.wrtmonitor.app.api.dto.AutomationRunDto
import ru.wrtmonitor.app.api.dto.AutomationTemplateDto
import ru.wrtmonitor.app.api.dto.EventDto
import ru.wrtmonitor.app.api.dto.NotificationRuleDto
import ru.wrtmonitor.app.api.isUnauthorized
import ru.wrtmonitor.app.data.RouterRepository

data class OperationsUiState(
    val loading: Boolean = false,
    val events: List<EventDto> = emptyList(),
    val notificationRules: List<NotificationRuleDto> = emptyList(),
    val automationRules: List<AutomationRuleDto> = emptyList(),
    val templates: List<AutomationTemplateDto> = emptyList(),
    val runs: List<AutomationRunDto> = emptyList(),
    val error: String? = null,
    val sessionExpired: Boolean = false,
)

class OperationsViewModel(
    private val repository: RouterRepository,
    private val deviceId: String,
) : ViewModel() {
    var state by mutableStateOf(OperationsUiState())
        private set

    fun refresh() {
        state = state.copy(loading = true, error = null)
        viewModelScope.launch {
            val events = async { repository.events(deviceId) }
            val notificationRules = async { repository.notificationRules() }
            val automationRules = async { repository.automationRules() }
            val templates = async { repository.automationTemplates() }
            val runs = async { repository.automationRuns() }
            val eventResult = events.await()
            val notificationResult = notificationRules.await()
            val automationResult = automationRules.await()
            val templateResult = templates.await()
            val runResult = runs.await()
            val error = listOfNotNull(
                eventResult as? ApiResult.Error,
                notificationResult as? ApiResult.Error,
                automationResult as? ApiResult.Error,
                templateResult as? ApiResult.Error,
                runResult as? ApiResult.Error,
            ).firstOrNull()
            state = if (error != null) {
                state.copy(loading = false, error = error.message, sessionExpired = error.isUnauthorized())
            } else {
                OperationsUiState(
                    events = (eventResult as ApiResult.Success).data,
                    notificationRules = (notificationResult as ApiResult.Success).data,
                    automationRules = (automationResult as ApiResult.Success).data,
                    templates = (templateResult as ApiResult.Success).data,
                    runs = (runResult as ApiResult.Success).data,
                )
            }
        }
    }

    fun acknowledge(event: EventDto) = act { repository.acknowledgeEvent(event.id) }

    fun snooze(event: EventDto) = act { repository.snoozeEvent(event.id) }

    fun addInAppRule(name: String) = act { repository.createInAppNotificationRule(deviceId, name) }

    fun deleteNotification(rule: NotificationRuleDto) = act { repository.deleteNotificationRule(rule.id) }

    fun addAutomation(template: AutomationTemplateDto) = act { repository.createAutomation(deviceId, template) }

    fun toggleAutomation(rule: AutomationRuleDto) = act { repository.setAutomationEnabled(rule, !rule.enabled) }

    fun deleteAutomation(rule: AutomationRuleDto) = act { repository.deleteAutomationRule(rule.id) }

    private fun <T> act(block: suspend () -> ApiResult<T>) {
        state = state.copy(error = null)
        viewModelScope.launch {
            when (val result = block()) {
                is ApiResult.Success -> {
                    refresh()
                }
                is ApiResult.Error -> state = state.copy(
                    error = result.message,
                    sessionExpired = result.isUnauthorized(),
                )
            }
        }
    }
}
