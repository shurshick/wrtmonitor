package ru.wrtmonitor.app.ui.screens

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class UpdateStateTest {
    @Test
    fun publishedApkProducesDownloadAction() {
        val state = resolveUpdateState(
            currentVersion = "0.49.0",
            response = """[{"tag_name":"v0.50.0","draft":false,"html_url":"https://example.test/release","assets":[{"name":"wrtmonitor-v0.50.0.apk","browser_download_url":"https://example.test/app.apk"}]}]""",
        ) as UpdateState.Available

        assertEquals("0.50.0", state.latestVersion)
        assertEquals("https://example.test/app.apk", state.apkUrl)
        assertEquals("https://example.test/release", state.releasePageUrl)
    }

    @Test
    fun releaseWithoutApkKeepsReleasePageSeparate() {
        val state = resolveUpdateState(
            currentVersion = "0.49.0",
            response = """[{"tag_name":"v0.50.0","draft":false,"html_url":"https://example.test/release","assets":[]}]""",
        ) as UpdateState.Available

        assertNull(state.apkUrl)
        assertEquals("https://example.test/release", state.releasePageUrl)
    }

    @Test
    fun currentVersionIsUpToDate() {
        val state = resolveUpdateState(
            currentVersion = "0.50.0",
            response = """[{"tag_name":"v0.50.0","draft":false,"html_url":"https://example.test/release","assets":[]}]""",
        ) as UpdateState.UpToDate

        assertEquals("0.50.0", state.latestVersion)
    }
}
