package ru.wrtmonitor.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import ru.wrtmonitor.app.R
import ru.wrtmonitor.app.api.dto.JsonArray
import ru.wrtmonitor.app.api.dto.JsonObject
import ru.wrtmonitor.app.ui.components.ActionRow
import ru.wrtmonitor.app.ui.components.ExpandableSettingsCard
import ru.wrtmonitor.app.ui.components.PrimaryActionButton

@Composable
internal fun VpnControlSections(
    capabilities: Map<String, Boolean>,
    vpn: JsonObject?,
    wireGuard: WireGuardFormState,
    openVpn: OpenVpnFormState,
    policy: VpnPolicyFormState,
    successMessage: String,
    onCommand: (PendingSafeCommand) -> Unit,
) {
    if (capabilities["vpn.wireguard.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.wireguard_interface), wireGuard.name) {
            OutlinedTextField(wireGuard.name, wireGuard.onNameChange, label = { Text(stringResource(R.string.interface_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wireGuard.address, wireGuard.onAddressChange, label = { Text(stringResource(R.string.tunnel_address)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wireGuard.port, { wireGuard.onPortChange(it.filter(Char::isDigit)) }, label = { Text(stringResource(R.string.listen_port)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wireGuard.privateKey, wireGuard.onPrivateKeyChange, label = { Text(stringResource(R.string.private_key_optional)) }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow {
                PrimaryActionButton(stringResource(R.string.save), {
                    onCommand(PendingSafeCommand("vpn.wireguard.set_interface", JsonObject().put("name", wireGuard.name).put("enabled", true).put("mode", "server").put("addresses", JsonArray(listOf(wireGuard.address))).put("listen_port", wireGuard.port.toIntOrNull() ?: 51820).put("private_key", wireGuard.privateKey).put("mtu", 1420), successMessage))
                }, enabled = wireGuard.name.isNotBlank() && wireGuard.address.isNotBlank())
                TextButton({ onCommand(PendingSafeCommand("vpn.wireguard.delete_interface", JsonObject().put("name", wireGuard.name), successMessage)) }, enabled = wireGuard.name.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
        ExpandableSettingsCard(stringResource(R.string.wireguard_peer), wireGuard.peerName) {
            OutlinedTextField(wireGuard.name, wireGuard.onNameChange, label = { Text(stringResource(R.string.interface_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wireGuard.peerName, wireGuard.onPeerNameChange, label = { Text(stringResource(R.string.peer_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wireGuard.peerPublicKey, wireGuard.onPeerPublicKeyChange, label = { Text(stringResource(R.string.public_key)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wireGuard.peerPresharedKey, wireGuard.onPeerPresharedKeyChange, label = { Text(stringResource(R.string.preshared_key_optional)) }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wireGuard.peerAllowedIps, wireGuard.onPeerAllowedIpsChange, label = { Text(stringResource(R.string.allowed_ips)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(wireGuard.peerEndpoint, wireGuard.onPeerEndpointChange, label = { Text(stringResource(R.string.endpoint_optional)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            PrimaryActionButton(stringResource(R.string.save), {
                onCommand(PendingSafeCommand("vpn.wireguard.set_peer", JsonObject().put("interface", wireGuard.name).put("name", wireGuard.peerName).put("public_key", wireGuard.peerPublicKey).put("preshared_key", wireGuard.peerPresharedKey).put("allowed_ips", JsonArray(listOf(wireGuard.peerAllowedIps))).put("endpoint", wireGuard.peerEndpoint).put("persistent_keepalive", 25).put("route_allowed_ips", true), successMessage))
            }, Modifier.align(Alignment.End), enabled = wireGuard.peerName.isNotBlank() && wireGuard.peerPublicKey.isNotBlank())
            ActionRow {
                TextButton({ onCommand(PendingSafeCommand("vpn.wireguard.export_peer", JsonObject().put("interface", wireGuard.name).put("name", wireGuard.peerName), successMessage)) }, enabled = wireGuard.peerName.isNotBlank()) { Text(stringResource(R.string.export)) }
                TextButton({ onCommand(PendingSafeCommand("vpn.wireguard.delete_peer", JsonObject().put("interface", wireGuard.name).put("name", wireGuard.peerName), successMessage)) }, enabled = wireGuard.peerName.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
    }
    if (capabilities["vpn.openvpn.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.openvpn_client), openVpn.name) {
            val clients = vpn?.optJsonObject("openvpn")?.optJsonArray("clients") ?: JsonArray()
            for (index in 0 until clients.length()) {
                val item = clients.optJsonObject(index) ?: continue
                val name = item.optString("name")
                val enabled = item.optBoolean("enabled")
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(name, style = MaterialTheme.typography.titleSmall)
                        Text(if (item.optBoolean("runtime")) stringResource(R.string.connected) else stringResource(if (enabled) R.string.enabled_value else R.string.disabled_value), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    TextButton({ onCommand(PendingSafeCommand("vpn.openvpn.set_enabled", JsonObject().put("name", name).put("enabled", !enabled), successMessage)) }) { Text(stringResource(if (enabled) R.string.disable_action else R.string.enable_action)) }
                    if (item.optBoolean("export_available")) TextButton({ onCommand(PendingSafeCommand("vpn.openvpn.export_client", JsonObject().put("name", name), successMessage)) }) { Text(stringResource(R.string.export)) }
                }
                if (index < clients.length() - 1) HorizontalDivider()
            }
            OutlinedTextField(openVpn.name, openVpn.onNameChange, label = { Text(stringResource(R.string.profile_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(openVpn.config, openVpn.onConfigChange, label = { Text(stringResource(R.string.openvpn_config)) }, modifier = Modifier.fillMaxWidth(), minLines = 6)
            ActionRow {
                PrimaryActionButton(stringResource(R.string.import_profile), { onCommand(PendingSafeCommand("vpn.openvpn.set_client", JsonObject().put("name", openVpn.name).put("enabled", true).put("config", openVpn.config), successMessage)) }, enabled = openVpn.name.isNotBlank() && openVpn.config.isNotBlank())
                TextButton({ onCommand(PendingSafeCommand("vpn.openvpn.delete_client", JsonObject().put("name", openVpn.name), successMessage)) }, enabled = openVpn.name.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
    }
    if (capabilities["vpn.policy.configure"] == true) {
        ExpandableSettingsCard(stringResource(R.string.policy_routing), policy.name) {
            OutlinedTextField(policy.name, policy.onNameChange, label = { Text(stringResource(R.string.rule_name)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(policy.networkInterface, policy.onInterfaceChange, label = { Text(stringResource(R.string.vpn_interface)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(policy.source, policy.onSourceChange, label = { Text(stringResource(R.string.policy_source)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(policy.destination, policy.onDestinationChange, label = { Text(stringResource(R.string.policy_destination)) }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            ActionRow {
                PrimaryActionButton(stringResource(R.string.save), { onCommand(PendingSafeCommand("vpn.policy.set", JsonObject().put("name", policy.name).put("enabled", true).put("interface", policy.networkInterface).put("source", policy.source).put("destination", policy.destination).put("protocol", "all"), successMessage)) }, enabled = policy.name.isNotBlank() && policy.networkInterface.isNotBlank() && (policy.source.isNotBlank() || policy.destination.isNotBlank()))
                TextButton({ onCommand(PendingSafeCommand("vpn.policy.delete", JsonObject().put("name", policy.name), successMessage)) }, enabled = policy.name.isNotBlank()) { Text(stringResource(R.string.delete)) }
            }
        }
    }
}

internal data class WireGuardFormState(
    val name: String, val address: String, val port: String, val privateKey: String,
    val peerName: String, val peerPublicKey: String, val peerPresharedKey: String,
    val peerAllowedIps: String, val peerEndpoint: String,
    val onNameChange: (String) -> Unit, val onAddressChange: (String) -> Unit,
    val onPortChange: (String) -> Unit, val onPrivateKeyChange: (String) -> Unit,
    val onPeerNameChange: (String) -> Unit, val onPeerPublicKeyChange: (String) -> Unit,
    val onPeerPresharedKeyChange: (String) -> Unit, val onPeerAllowedIpsChange: (String) -> Unit,
    val onPeerEndpointChange: (String) -> Unit,
)

internal data class OpenVpnFormState(val name: String, val config: String, val onNameChange: (String) -> Unit, val onConfigChange: (String) -> Unit)
internal data class VpnPolicyFormState(val name: String, val networkInterface: String, val source: String, val destination: String, val onNameChange: (String) -> Unit, val onInterfaceChange: (String) -> Unit, val onSourceChange: (String) -> Unit, val onDestinationChange: (String) -> Unit)
