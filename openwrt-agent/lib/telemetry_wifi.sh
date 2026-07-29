wireless_section_name() {
    section_type="$1"
    section_index="$2"
    uci -q show wireless 2>/dev/null \
        | sed -n "s/^wireless\.\([^.=]*\)=$section_type$/\1/p" \
        | sed -n "$((section_index + 1))p"
}

wifi_schedule_json() {
    requested_radio="$1"
    schedule_index=0
    while uci -q get "wrtmonitor.@wifi_schedule[$schedule_index]" >/dev/null 2>&1; do
        schedule_radio="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].radio" 2>/dev/null || true)"
        if [ "$schedule_radio" = "$requested_radio" ]; then
            schedule_enabled="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].enabled" 2>/dev/null || echo 0)"
            schedule_start="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].start" 2>/dev/null || true)"
            schedule_stop="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].stop" 2>/dev/null || true)"
            schedule_days="$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].weekdays" 2>/dev/null || true)"
            days_json=""
            for schedule_day in $schedule_days; do
                [ -n "$days_json" ] && days_json="$days_json,"
                days_json="$days_json\"$(json_escape "$schedule_day")\""
            done
            printf '{"enabled":%s,"weekdays":[%s],"start":"%s","stop":"%s"}' \
                "$( [ "$schedule_enabled" = "1" ] && printf true || printf false )" \
                "$days_json" "$(json_escape "$schedule_start")" "$(json_escape "$schedule_stop")"
            return 0
        fi
        schedule_index=$((schedule_index + 1))
    done
    printf '{"enabled":false,"weekdays":[],"start":"","stop":""}'
}

wifi_stations_json() {
    station_groups=""
    if command -v ubus >/dev/null 2>&1; then
        for hostapd_object in $(ubus list 'hostapd.*' 2>/dev/null || true); do
            station_interface="${hostapd_object#hostapd.}"
            station_response="$(ubus call "$hostapd_object" get_clients 2>/dev/null || true)"
            [ -n "$station_response" ] || continue
            station_file="/tmp/wrtmonitor-stations-$$"
            printf '%s' "$station_response" >"$station_file"
            station_clients="$(jsonfilter -i "$station_file" -e '@.clients' 2>/dev/null || printf '{}')"
            rm -f "$station_file"
            case "$station_clients" in \{*\}) ;; *) station_clients='{}' ;; esac
            station_ssid=""
            station_band=""
            if command -v iwinfo >/dev/null 2>&1; then
                station_info="$(iwinfo "$station_interface" info 2>/dev/null || true)"
                station_ssid="$(printf '%s\n' "$station_info" | sed -n 's/.*ESSID: "\(.*\)".*/\1/p' | head -n 1)"
                case "$station_info" in
                    *" GHz"*)
                        station_frequency="$(printf '%s\n' "$station_info" | sed -n 's/.*(\([0-9][0-9]*\.[0-9][0-9]*\) GHz).*/\1/p' | head -n 1)"
                        case "$station_frequency" in 2.*) station_band="2g" ;; 5.*) station_band="5g" ;; 6.*) station_band="6g" ;; esac
                        ;;
                esac
            fi
            [ -n "$station_groups" ] && station_groups="$station_groups,"
            station_groups="$station_groups{\"interface\":\"$(json_escape "$station_interface")\",\"ssid\":\"$(json_escape "$station_ssid")\",\"band\":\"$(json_escape "$station_band")\",\"clients\":$station_clients}"
        done
    fi
    printf '[%s]' "$station_groups"
}

wifi_radio_ifname() {
    requested_radio="$1"
    radio_index="$2"
    if command -v wifi >/dev/null 2>&1 && command -v jsonfilter >/dev/null 2>&1; then
        status_file="/tmp/wrtmonitor-wifi-status-$$"
        wifi status "$requested_radio" >"$status_file" 2>/dev/null || true
        runtime_ifname="$(jsonfilter -i "$status_file" -e "@.$requested_radio.interfaces[0].ifname" 2>/dev/null || true)"
        rm -f "$status_file"
        [ -n "$runtime_ifname" ] && {
            printf '%s' "$runtime_ifname"
            return 0
        }
    fi
    if command -v iw >/dev/null 2>&1; then
        iw dev 2>/dev/null | awk '$1 == "Interface" {print $2}' | sed -n "$((radio_index + 1))p"
    fi
}

wifi_survey_json() {
    survey_interface="$1"
    if ! command -v iw >/dev/null 2>&1; then
        printf '{"state":"unsupported","reason":"iw_unavailable","interface":"","frequency_mhz":null,"noise_dbm":null,"active_ms":null,"busy_ms":null,"rx_ms":null,"tx_ms":null,"utilization_percent":null}'
        return 0
    fi
    if [ -z "$survey_interface" ]; then
        printf '{"state":"unsupported","reason":"interface_unavailable","interface":"","frequency_mhz":null,"noise_dbm":null,"active_ms":null,"busy_ms":null,"rx_ms":null,"tx_ms":null,"utilization_percent":null}'
        return 0
    fi
    survey_values="$(iw dev "$survey_interface" survey dump 2>/dev/null | awk '
        /frequency:/ {
            capture = index($0, "[in use]") > 0
            if (capture) {
                frequency = $2; noise = ""; active = ""; busy = ""; receive = ""; transmit = ""
            }
            next
        }
        capture && /noise:/ { noise = $2; next }
        capture && /channel active time:/ { active = $(NF-1); next }
        capture && /channel busy time:/ { busy = $(NF-1); next }
        capture && /channel receive time:/ { receive = $(NF-1); next }
        capture && /channel transmit time:/ { transmit = $(NF-1); next }
        END {
            if (frequency != "") print frequency "|" noise "|" active "|" busy "|" receive "|" transmit
        }
    ' | head -n 1)"
    if [ -z "$survey_values" ]; then
        printf '{"state":"unsupported","reason":"driver_did_not_report_survey","interface":"%s","frequency_mhz":null,"noise_dbm":null,"active_ms":null,"busy_ms":null,"rx_ms":null,"tx_ms":null,"utilization_percent":null}' "$(json_escape "$survey_interface")"
        return 0
    fi
    IFS='|' read -r survey_frequency survey_noise survey_active survey_busy survey_rx survey_tx <<EOF
$survey_values
EOF
    case "$survey_frequency" in ''|*[!0-9]*) survey_frequency=null ;; esac
    case "$survey_noise" in ''|'-'|*[!0-9-]*) survey_noise=null ;; esac
    case "$survey_active" in ''|*[!0-9]*) survey_active=null ;; esac
    case "$survey_busy" in ''|*[!0-9]*) survey_busy=null ;; esac
    case "$survey_rx" in ''|*[!0-9]*) survey_rx=null ;; esac
    case "$survey_tx" in ''|*[!0-9]*) survey_tx=null ;; esac
    survey_utilization=null
    if [ "$survey_active" != null ] && [ "$survey_busy" != null ] && [ "$survey_active" -gt 0 ]; then
        survey_utilization=$((survey_busy * 100 / survey_active))
        [ "$survey_utilization" -gt 100 ] && survey_utilization=100
    fi
    printf '{"state":"observed","reason":"","interface":"%s","frequency_mhz":%s,"noise_dbm":%s,"active_ms":%s,"busy_ms":%s,"rx_ms":%s,"tx_ms":%s,"utilization_percent":%s}' \
        "$(json_escape "$survey_interface")" "$survey_frequency" "$survey_noise" "$survey_active" "$survey_busy" "$survey_rx" "$survey_tx" "$survey_utilization"
}

wifi_status_json() {
    radios=""
    index=0
    while uci -q get "wireless.@wifi-device[$index]" >/dev/null 2>&1; do
        name="$(wireless_section_name wifi-device "$index")"
        [ -n "$name" ] || name="radio$index"
        disabled="$(uci -q get "wireless.@wifi-device[$index].disabled" 2>/dev/null || echo 0)"
        channel="$(uci -q get "wireless.@wifi-device[$index].channel" 2>/dev/null || true)"
        band="$(uci -q get "wireless.@wifi-device[$index].band" 2>/dev/null || true)"
        ssids=""
        interfaces=""
        encryption=""
        iface_index=0
        while uci -q get "wireless.@wifi-iface[$iface_index]" >/dev/null 2>&1; do
            iface_device="$(uci -q get "wireless.@wifi-iface[$iface_index].device" 2>/dev/null || true)"
            if [ "$iface_device" = "$name" ]; then
                iface_name="$(wireless_section_name wifi-iface "$iface_index")"
                [ -n "$iface_name" ] || iface_name="@wifi-iface[$iface_index]"
                ssid="$(uci -q get "wireless.@wifi-iface[$iface_index].ssid" 2>/dev/null || true)"
                encryption="$(uci -q get "wireless.@wifi-iface[$iface_index].encryption" 2>/dev/null || true)"
                mode="$(uci -q get "wireless.@wifi-iface[$iface_index].mode" 2>/dev/null || true)"
                network="$(uci -q get "wireless.@wifi-iface[$iface_index].network" 2>/dev/null || true)"
                hidden="$(uci -q get "wireless.@wifi-iface[$iface_index].hidden" 2>/dev/null || echo 0)"
                isolate="$(uci -q get "wireless.@wifi-iface[$iface_index].isolate" 2>/dev/null || echo 0)"
                iface_disabled="$(uci -q get "wireless.@wifi-iface[$iface_index].disabled" 2>/dev/null || echo 0)"
                ieee80211r="$(uci -q get "wireless.@wifi-iface[$iface_index].ieee80211r" 2>/dev/null || echo 0)"
                ieee80211k="$(uci -q get "wireless.@wifi-iface[$iface_index].ieee80211k" 2>/dev/null || echo 0)"
                bss_transition="$(uci -q get "wireless.@wifi-iface[$iface_index].bss_transition" 2>/dev/null || echo 0)"
                mobility_domain="$(uci -q get "wireless.@wifi-iface[$iface_index].mobility_domain" 2>/dev/null || true)"
                mesh_id="$(uci -q get "wireless.@wifi-iface[$iface_index].mesh_id" 2>/dev/null || true)"
                if [ -n "$ssid" ]; then
                    [ -n "$ssids" ] && ssids="$ssids,"
                    ssids="$ssids\"$(json_escape "$ssid")\""
                fi
                [ -n "$interfaces" ] && interfaces="$interfaces,"
                interfaces="$interfaces{\"id\":\"$(json_escape "$iface_name")\",\"index\":$iface_index,\"ssid\":\"$(json_escape "$ssid")\",\"enabled\":$( [ "$iface_disabled" = "1" ] && printf false || printf true ),\"encryption\":\"$(json_escape "$encryption")\",\"mode\":\"$(json_escape "$mode")\",\"network\":\"$(json_escape "$network")\",\"hidden\":$( [ "$hidden" = "1" ] && printf true || printf false ),\"isolate\":$( [ "$isolate" = "1" ] && printf true || printf false ),\"ieee80211r\":$( [ "$ieee80211r" = "1" ] && printf true || printf false ),\"ieee80211k\":$( [ "$ieee80211k" = "1" ] && printf true || printf false ),\"bss_transition\":$( [ "$bss_transition" = "1" ] && printf true || printf false ),\"mobility_domain\":\"$(json_escape "$mobility_domain")\",\"mesh_id\":\"$(json_escape "$mesh_id")\"}"
            fi
            iface_index=$((iface_index + 1))
        done
        up=true
        [ "$disabled" = "1" ] && up=false
        radio="{\"id\":\"$name\",\"name\":\"$name\",\"up\":$up,\"disabled\":$( [ "$disabled" = "1" ] && printf true || printf false ),\"ssid\":[$ssids],\"interfaces\":[${interfaces}]"
        [ -n "$channel" ] && radio="$radio,\"channel\":\"$(json_escape "$channel")\""
        [ -n "$band" ] && radio="$radio,\"band\":\"$(json_escape "$band")\""
        country="$(uci -q get "wireless.@wifi-device[$index].country" 2>/dev/null || true)"
        htmode="$(uci -q get "wireless.@wifi-device[$index].htmode" 2>/dev/null || true)"
        txpower="$(uci -q get "wireless.@wifi-device[$index].txpower" 2>/dev/null || true)"
        [ -n "$country" ] && radio="$radio,\"country\":\"$(json_escape "$country")\""
        [ -n "$htmode" ] && radio="$radio,\"htmode\":\"$(json_escape "$htmode")\""
        [ -n "$txpower" ] && radio="$radio,\"txpower\":\"$(json_escape "$txpower")\""
        [ -n "${encryption:-}" ] && radio="$radio,\"encryption\":\"$(json_escape "$encryption")\""
        radio="$radio,\"schedule\":$(wifi_schedule_json "$name")"
        runtime_ifname="$(wifi_radio_ifname "$name" "$index")"
        radio="$radio,\"survey\":$(wifi_survey_json "$runtime_ifname")"
        radio="$radio}"
        [ -n "$radios" ] && radios="$radios,"
        radios="$radios$radio"
        index=$((index + 1))
    done
    if [ "$index" -gt 0 ]; then
        printf '{"available":true,"radios":[%s],"stations":%s}' "$radios" "$(wifi_stations_json)"
    else
        printf '{"available":false,"radios":[],"stations":[]}'
    fi
}
