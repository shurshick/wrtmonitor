package ru.wrtmonitor.app

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AppLaunchTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Before
    fun resetSession() {
        composeRule.activity.getSharedPreferences("wrtmonitor", 0).edit().clear().commit()
        composeRule.activityRule.scenario.recreate()
    }

    @Test
    fun cleanInstallShowsServerSetup() {
        composeRule.onNodeWithText("WrtMonitor").assertIsDisplayed()
    }
}
