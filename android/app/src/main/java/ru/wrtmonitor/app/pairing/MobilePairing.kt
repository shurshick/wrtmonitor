package ru.wrtmonitor.app.pairing

import org.json.JSONObject
import java.net.URI

const val MOBILE_PAIRING_TYPE = "wrtmonitor-mobile-setup"
const val MOBILE_PAIRING_VERSION = 1

data class MobilePairingSetup(
    val serverUrl: String,
    val pairingToken: String,
) {
    val secure: Boolean get() = serverUrl.startsWith("https://", ignoreCase = true)
}

class MobilePairingPayloadException(val code: String) : IllegalArgumentException(code)

fun parseMobilePairingPayload(raw: String): MobilePairingSetup {
    val payload = runCatching { JSONObject(raw) }
        .getOrElse { throw MobilePairingPayloadException("invalid_json") }
    if (payload.optString("type") != MOBILE_PAIRING_TYPE) {
        throw MobilePairingPayloadException("invalid_type")
    }
    if (payload.optInt("version", -1) != MOBILE_PAIRING_VERSION) {
        throw MobilePairingPayloadException("unsupported_version")
    }
    val serverUrl = normalizePairingServerUrl(payload.optString("server_url"))
    val token = payload.optString("pairing_token")
    if (!token.matches(Regex("^[A-Za-z0-9_-]{32,256}$"))) {
        throw MobilePairingPayloadException("invalid_token")
    }
    return MobilePairingSetup(serverUrl, token)
}

fun normalizePairingServerUrl(value: String): String {
    val trimmed = value.trim().trimEnd('/')
    val uri = runCatching { URI(trimmed) }
        .getOrElse { throw MobilePairingPayloadException("invalid_server_url") }
    val scheme = uri.scheme?.lowercase()
    val host = uri.host?.lowercase()
    if (scheme !in setOf("http", "https") || host.isNullOrBlank() ||
        uri.userInfo != null || uri.fragment != null || uri.query != null ||
        (uri.path?.let { it.isNotBlank() && it != "/" } == true)
    ) {
        throw MobilePairingPayloadException("invalid_server_url")
    }
    if (scheme == "http" && !isLocalHost(host)) {
        throw MobilePairingPayloadException("insecure_remote_server")
    }
    return trimmed
}

private fun isLocalHost(host: String): Boolean {
    if (host == "localhost" || host == "::1" || host.startsWith("fe80:") ||
        host.startsWith("fc") || host.startsWith("fd")) return true
    val octets = host.split('.').mapNotNull(String::toIntOrNull)
    if (octets.size != 4 || octets.any { it !in 0..255 }) return false
    return octets[0] == 10 || octets[0] == 127 ||
        (octets[0] == 169 && octets[1] == 254) ||
        (octets[0] == 172 && octets[1] in 16..31) ||
        (octets[0] == 192 && octets[1] == 168)
}
