package ru.wrtmonitor.app.api

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import ru.wrtmonitor.app.domain.AgentUpdateState

class AgentUpdateParsingTest {
    @Test fun oldSourceOnOlderServerIsNotAnUpdateOrError() {
        val agent = parseAgentStatus(JSONObject("""{"version":"1.0.0","available_version":"0.55.5","last_update_status":"skipped","last_update_error":"downgrade blocked"}"""))
        assertEquals(AgentUpdateState.SourceOlder, agent.updateView.state)
        assertNull(agent.updateView.availableVersion)
        assertNull(agent.updateView.error)
        assertEquals("downgrade blocked", agent.lastUpdateError)
    }

    @Test fun equalAndNewerSourcesAreDifferentStates() {
        for ((source, state) in listOf("1.0.0" to AgentUpdateState.Current, "1.0.1" to AgentUpdateState.Available, "1.0.0-rc1" to AgentUpdateState.SourceOlder)) {
            val agent = parseAgentStatus(JSONObject().put("version", "1.0.0").put("available_version", source))
            assertEquals(state, agent.updateView.state)
            assertEquals(if (state == AgentUpdateState.Available) source else null, agent.updateView.availableVersion)
        }
        assertEquals(AgentUpdateState.Available, parseAgentStatus(JSONObject("""{"version":"1.0.0-rc1","available_version":"1.0.0"}""")).updateView.state)
    }

    @Test fun signatureFailureRemainsVisible() {
        val agent = parseAgentStatus(JSONObject("""{"version":"1.0.0","available_version":"0.55.5","last_update_status":"failed","last_update_error":"checksum or syntax verification failed"}"""))
        assertEquals(AgentUpdateState.Error, agent.updateView.state)
        assertEquals("checksum or syntax verification failed", agent.updateView.error)
    }

    @Test fun serverViewOverridesHistoricalRawFields() {
        val agent = parseAgentStatus(JSONObject("""{"version":"1.0.0","available_version":"0.55.5","last_update_error":"downgrade blocked","update_view":{"state":"source_older","source_version":"0.55.5","available_version":null,"error":null}}"""))
        assertEquals(AgentUpdateState.SourceOlder, agent.updateView.state)
        assertNull(agent.updateView.availableVersion)
        assertNull(agent.updateView.error)
    }

    @Test fun malformedAndUnknownVersionsDoNotInventUpdates() {
        for (version in listOf("development", "999999999999999999999999.0.0", "null")) {
            assertEquals(AgentUpdateState.Unknown, parseAgentStatus(JSONObject().put("version", version).put("available_version", "1.0.1")).updateView.state)
        }
        assertEquals(AgentUpdateState.Unknown, parseAgentStatus(JSONObject("""{"update_view":{"state":"future","available_version":"1.0.1"}}""")).updateView.state)
    }
}
