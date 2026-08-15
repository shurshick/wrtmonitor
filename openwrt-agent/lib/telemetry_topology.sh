json_word_list() {
    values="$1"
    output=""
    set -f
    for value in $values; do
        [ -n "$output" ] && output="$output,"
        output="$output\"$(json_escape "$value")\""
    done
    set +f
    printf '[%s]' "$output"
}

network_topology_json() {
    segments=""
    for section in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^.=]*\)=interface$/\1/p'); do
        proto="$(uci -q get "network.$section.proto" 2>/dev/null || true)"
        device="$(uci -q get "network.$section.device" 2>/dev/null || uci -q get "network.$section.ifname" 2>/dev/null || true)"
        ipaddr="$(uci -q get "network.$section.ipaddr" 2>/dev/null || true)"
        netmask="$(uci -q get "network.$section.netmask" 2>/dev/null || true)"
        ip6assign="$(uci -q get "network.$section.ip6assign" 2>/dev/null || true)"
        ip6hint="$(uci -q get "network.$section.ip6hint" 2>/dev/null || true)"
        disabled="$(uci -q get "network.$section.disabled" 2>/dev/null || echo 0)"
        dhcp_start="$(uci -q get "dhcp.$section.start" 2>/dev/null || true)"
        dhcp_limit="$(uci -q get "dhcp.$section.limit" 2>/dev/null || true)"
        dhcp_leasetime="$(uci -q get "dhcp.$section.leasetime" 2>/dev/null || true)"
        dhcp_ignore="$(uci -q get "dhcp.$section.ignore" 2>/dev/null || echo 0)"
        bridge_section=""
        if [ -n "$device" ]; then
            for candidate in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^.=]*\)=device$/\1/p'); do
                [ "$(uci -q get "network.$candidate.type" 2>/dev/null || true)" = bridge ] || continue
                [ "$(uci -q get "network.$candidate.name" 2>/dev/null || true)" = "$device" ] || continue
                bridge_section="$candidate"
                break
            done
        fi
        segment_policy=isolated
        for zone_ref in $(uci -q show firewall 2>/dev/null | sed -n 's/^firewall\.\([^=]*\)=zone$/\1/p'); do
            zone_name="$(uci -q get "firewall.$zone_ref.name" 2>/dev/null || true)"
            zone_networks="$(uci -q get "firewall.$zone_ref.network" 2>/dev/null || true)"
            zone_matches=false
            [ "$zone_name" = "$section" ] && zone_matches=true
            for zone_network in $zone_networks; do [ "$zone_network" != "$section" ] || zone_matches=true; done
            [ "$zone_matches" = true ] || continue
            if [ "$(uci -q get "firewall.$zone_ref.input" 2>/dev/null || true)" = ACCEPT ]; then
                segment_policy=trusted
            else
                for forwarding_ref in $(uci -q show firewall 2>/dev/null | sed -n 's/^firewall\.\([^=]*\)=forwarding$/\1/p'); do
                    [ "$(uci -q get "firewall.$forwarding_ref.src" 2>/dev/null || true)" = "$zone_name" ] || continue
                    [ "$(uci -q get "firewall.$forwarding_ref.dest" 2>/dev/null || true)" = wan ] || continue
                    segment_policy=guest
                    break
                done
            fi
            break
        done
        [ -n "$segments" ] && segments="$segments,"
        segments="$segments{\"name\":\"$(json_escape "$section")\",\"proto\":\"$(json_escape "$proto")\",\"device\":\"$(json_escape "$device")\",\"bridge_section\":\"$(json_escape "$bridge_section")\",\"ip_address\":\"$(json_escape "$ipaddr")\",\"netmask\":\"$(json_escape "$netmask")\",\"ip6assign\":\"$(json_escape "$ip6assign")\",\"ip6hint\":\"$(json_escape "$ip6hint")\",\"policy\":\"$(json_escape "$segment_policy")\",\"enabled\":$( [ "$disabled" = 1 ] && printf false || printf true ),\"dhcp\":{\"enabled\":$( [ "$dhcp_ignore" = 1 ] || [ -z "$dhcp_start" ] && printf false || printf true ),\"start\":\"$(json_escape "$dhcp_start")\",\"limit\":\"$(json_escape "$dhcp_limit")\",\"leasetime\":\"$(json_escape "$dhcp_leasetime")\"}}"
    done

    bridges=""
    for section in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^.=]*\)=device$/\1/p'); do
        type="$(uci -q get "network.$section.type" 2>/dev/null || true)"
        [ "$type" = bridge ] || continue
        name="$(uci -q get "network.$section.name" 2>/dev/null || echo "$section")"
        ports="$(uci -q get "network.$section.ports" 2>/dev/null || true)"
        stp="$(uci -q get "network.$section.stp" 2>/dev/null || echo 0)"
        igmp="$(uci -q get "network.$section.igmp_snooping" 2>/dev/null || echo 0)"
        vlan_filtering="$(uci -q get "network.$section.vlan_filtering" 2>/dev/null || echo 0)"
        [ -n "$bridges" ] && bridges="$bridges,"
        bridges="$bridges{\"section\":\"$(json_escape "$section")\",\"name\":\"$(json_escape "$name")\",\"ports\":$(json_word_list "$ports"),\"stp\":$( [ "$stp" = 1 ] && printf true || printf false ),\"igmp_snooping\":$( [ "$igmp" = 1 ] && printf true || printf false ),\"vlan_filtering\":$( [ "$vlan_filtering" = 1 ] && printf true || printf false )}"
    done

    vlans=""
    for ref in $(uci -q show network 2>/dev/null | sed -n 's/^network\.\([^=]*\)=bridge-vlan$/\1/p'); do
        device="$(uci -q get "network.$ref.device" 2>/dev/null || true)"
        vlan_id="$(uci -q get "network.$ref.vlan" 2>/dev/null || true)"
        ports="$(uci -q get "network.$ref.ports" 2>/dev/null || true)"
        case "$vlan_id" in ''|*[!0-9]*) vlan_id=null ;; esac
        [ -n "$vlans" ] && vlans="$vlans,"
        vlans="$vlans{\"section\":\"$(json_escape "$ref")\",\"device\":\"$(json_escape "$device")\",\"vlan_id\":$vlan_id,\"ports\":$(json_word_list "$ports")}"
    done
    printf '{"segments":[%s],"bridges":[%s],"vlans":[%s]}' "$segments" "$bridges" "$vlans"
}
