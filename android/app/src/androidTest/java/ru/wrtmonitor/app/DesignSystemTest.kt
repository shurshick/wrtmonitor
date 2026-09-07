package ru.wrtmonitor.app

import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.wrtmonitor.app.ui.components.PrimaryActionButton
import ru.wrtmonitor.app.ui.components.WrtStatusBadge
import ru.wrtmonitor.app.ui.theme.WrtMonitorTheme
import ru.wrtmonitor.app.ui.theme.WrtStatus

@RunWith(AndroidJUnit4::class)
class DesignSystemTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun primaryActionKeepsAccessibleTouchTarget() {
        composeRule.setContent {
            WrtMonitorTheme(darkTheme = true) {
                PrimaryActionButton("Action", {}, modifier = androidx.compose.ui.Modifier.testTag("primary-action"))
            }
        }

        composeRule.onNodeWithTag("primary-action").assertHeightIsAtLeast(48.dp)
    }

    @Test
    fun statusIsReadableWithoutColor() {
        composeRule.setContent {
            WrtMonitorTheme(darkTheme = false) {
                WrtStatusBadge("Offline", WrtStatus.Offline)
            }
        }

        composeRule.onNodeWithText("Offline").assertIsDisplayed()
    }
}
