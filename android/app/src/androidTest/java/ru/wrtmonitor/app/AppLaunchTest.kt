package ru.wrtmonitor.app

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.lifecycle.Lifecycle
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.wrtmonitor.app.data.SessionStore

@RunWith(AndroidJUnit4::class)
class AppLaunchTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Before
    fun resetSession() {
        SessionStore(composeRule.activity).clearAll()
        composeRule.activityRule.scenario.recreate()
    }

    @Test
    fun cleanInstallShowsServerSetup() {
        composeRule.onNodeWithText("WrtMonitor").assertIsDisplayed()
    }

    @Test
    fun setupRouteSurvivesActivityRecreation() {
        composeRule.onNodeWithText("WrtMonitor").assertIsDisplayed()
        composeRule.activityRule.scenario.recreate()
        composeRule.onNodeWithText("WrtMonitor").assertIsDisplayed()
    }

    @Test
    fun encryptedSessionSurvivesStoreAndActivityRecreation() {
        val original = SessionStore(composeRule.activity)
        original.saveSession(
            "https://monitor.example.test",
            "access-token",
            "refresh-token",
        )
        composeRule.activityRule.scenario.recreate()
        val restored = SessionStore(composeRule.activity)
        assertEquals("https://monitor.example.test", restored.serverUrl)
        assertEquals("access-token", restored.accessToken)
        assertEquals("refresh-token", restored.refreshToken)
    }

    @Test
    fun encryptedSessionSurvivesBackgroundAndResume() {
        val store = SessionStore(composeRule.activity)
        store.saveSession(
            "https://monitor.example.test",
            "access-token",
            "refresh-token",
        )
        composeRule.activityRule.scenario.moveToState(Lifecycle.State.CREATED)
        composeRule.activityRule.scenario.moveToState(Lifecycle.State.RESUMED)
        val restored = SessionStore(composeRule.activity)
        assertEquals("access-token", restored.accessToken)
        assertEquals("refresh-token", restored.refreshToken)
    }
}
