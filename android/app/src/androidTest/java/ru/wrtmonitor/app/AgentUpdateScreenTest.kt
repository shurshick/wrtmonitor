package ru.wrtmonitor.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertDoesNotExist
import androidx.compose.ui.test.assertExists
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.wrtmonitor.app.api.parseAgentStatus
import ru.wrtmonitor.app.ui.screens.AgentSection
import ru.wrtmonitor.app.ui.theme.WrtMonitorTheme

@RunWith(AndroidJUnit4::class)
class AgentUpdateScreenTest {
    @get:Rule val composeRule = createComposeRule()

    private fun showAgent(source: String, status: String, error: String) {
        val agent = parseAgentStatus(JSONObject().put("version", "1.0.1")
            .put("available_version", source).put("last_update_status", status).put("last_update_error", error))
        composeRule.setContent {
            WrtMonitorTheme(darkTheme = false) {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    AgentSection(agent, "", {}, {}, {}, {}, {}, {})
                }
            }
        }
    }

    private fun text(resource: Int) = InstrumentationRegistry.getInstrumentation().targetContext.getString(resource)

    @Test fun safeDowngradeRefusalIsNotAnErrorOrUpdate() {
        showAgent("0.55.5", "skipped", "downgrade blocked")
        composeRule.onNodeWithText(text(R.string.agent_update_source_older)).assertExists()
        composeRule.onNodeWithText(text(R.string.agent_update_none)).assertExists()
        composeRule.onNodeWithText("downgrade blocked").assertDoesNotExist()
    }

    @Test fun matchingSourceIsUpToDate() {
        showAgent("1.0.1", "skipped", "")
        composeRule.onNodeWithText(text(R.string.agent_update_current)).assertExists()
        composeRule.onNodeWithText(text(R.string.agent_update_none)).assertExists()
    }

    @Test fun signatureFailureIsStillShown() {
        showAgent("0.55.5", "failed", "checksum verification failed")
        composeRule.onNodeWithText(text(R.string.agent_update_failed)).assertExists()
        composeRule.onNodeWithText("checksum verification failed").assertExists()
    }
}
