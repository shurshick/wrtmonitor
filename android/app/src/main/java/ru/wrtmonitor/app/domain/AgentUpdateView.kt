package ru.wrtmonitor.app.domain

enum class AgentUpdateState(val wireValue: String) {
    Unknown("unknown"), Current("current"), Available("available"), SourceOlder("source_older"), Error("error");

    companion object {
        fun fromWire(value: String) = entries.firstOrNull { it.wireValue == value } ?: Unknown
    }
}

data class AgentUpdateView(
    val state: AgentUpdateState,
    val sourceVersion: String?,
    val availableVersion: String?,
    val error: String?,
)

private fun versionParts(value: String?): List<Long>? {
    val match = Regex("^v?(\\d+)\\.(\\d+)\\.(\\d+)(?:-rc(\\d+))?(?:\\+.*)?$")
        .matchEntire(value?.trim() ?: return null) ?: return null
    val parts = match.groupValues.drop(1)
    val numbers = parts.take(3).map { it.toLongOrNull() ?: return null }
    val rc = parts[3]
    return numbers + listOf(if (rc.isEmpty()) 1L else 0L, if (rc.isEmpty()) 0L else rc.toLongOrNull() ?: return null)
}

// Older servers expose the last observed source version, not necessarily an update.
fun legacyAgentUpdateView(installedVersion: String?, sourceVersion: String?, status: String?, rawError: String?): AgentUpdateView {
    val installed = versionParts(installedVersion)
    val source = versionParts(sourceVersion)
    val comparison = if (installed == null || source == null) null else {
        source.zip(installed).firstOrNull { (left, right) -> left != right }?.let { (left, right) -> left.compareTo(right) } ?: 0
    }
    val error = rawError?.trim()?.takeIf { it.isNotEmpty() && it != "null" }
    val blockedDowngrade = error == "downgrade blocked" && status == "skipped" && comparison != null && comparison < 0
    val state = when {
        status == "failed" || (error != null && !blockedDowngrade) -> AgentUpdateState.Error
        comparison == null -> AgentUpdateState.Unknown
        comparison > 0 -> AgentUpdateState.Available
        comparison == 0 -> AgentUpdateState.Current
        else -> AgentUpdateState.SourceOlder
    }
    return AgentUpdateView(state, sourceVersion, sourceVersion.takeIf { state == AgentUpdateState.Available }, error.takeIf { state == AgentUpdateState.Error })
}
