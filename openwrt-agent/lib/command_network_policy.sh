# shellcheck disable=SC2034,SC2154
handle_network_policy_command() {
    case "$command_type" in
        client.set_blocked)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"; client_mac="$(json_get_string "$payload_file" '@.mac')"; client_blocked="$(json_get_bool "$payload_file" '@.blocked')"; rm -f "$payload_file"
            client_ref="wrtmonitor_block_$(printf '%s' "$client_mac" | tr -d ':')"; backup_file="$(backup_config firewall "$command_id" "$command_type" || true)"
            if [ -z "$backup_file" ]; then status="failed"; result="$(command_failed_result "failed to create firewall backup")"
            elif [ "$client_blocked" = "true" ]; then
                if uci set "firewall.$client_ref=rule" && uci set "firewall.$client_ref.name=WrtMonitor block $client_mac" && uci set "firewall.$client_ref.src=lan" && uci set "firewall.$client_ref.dest=wan" && uci set "firewall.$client_ref.src_mac=$client_mac" && uci set "firewall.$client_ref.target=REJECT" && uci commit firewall && service_action firewall reload 20 >/dev/null 2>&1; then result="$(command_success_result "client internet access blocked" "\"backup\":\"$(json_escape "$backup_file")\",\"mac\":\"$(json_escape "$client_mac")\"")"; else status="failed"; result="$(command_failed_result "failed to block client")"; fi
            else
                uci -q delete "firewall.$client_ref" || true
                if uci commit firewall && service_action firewall reload 20 >/dev/null 2>&1; then result="$(command_success_result "client internet access restored" "\"backup\":\"$(json_escape "$backup_file")\",\"mac\":\"$(json_escape "$client_mac")\"")"; else status="failed"; result="$(command_failed_result "failed to unblock client")"; fi
            fi
            ;;
        client.set_policy)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"
            client_mac="$(json_get_string "$payload_file" '@.mac')"
            client_blocked="$(json_get_bool "$payload_file" '@.blocked')"
            schedule_enabled="$(json_get_bool "$payload_file" '@.schedule.enabled')"
            schedule_start="$(json_get_string "$payload_file" '@.schedule.start')"
            schedule_stop="$(json_get_string "$payload_file" '@.schedule.stop')"
            schedule_days="$(jsonfilter -i "$payload_file" -e '@.schedule.weekdays[*]' 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
            qos_priority="$(json_get_string "$payload_file" '@.qos.priority')"
            download_kbps="$(json_get_number "$payload_file" '@.qos.download_kbps')"
            upload_kbps="$(json_get_number "$payload_file" '@.qos.upload_kbps')"
            dns_provider="$(json_get_string "$payload_file" '@.dns.provider')"
            rm -f "$payload_file"
            [ -n "$qos_priority" ] || qos_priority=normal
            [ -n "$download_kbps" ] || download_kbps=0
            [ -n "$upload_kbps" ] || upload_kbps=0
            [ -n "$dns_provider" ] || dns_provider=none
            client_suffix="$(client_policy_suffix "$client_mac")"
            client_ref="wrtmonitor_policy_$client_suffix"
            client_after_ref="${client_ref}_after"
            client_days_ref="${client_ref}_days"
            qos_ref="wrtmonitor_qos_$client_suffix"
            dns_ref="wrtmonitor_dns_$client_suffix"
            dot_ref="wrtmonitor_dot_$client_suffix"
            shaping_device="$(client_policy_lan_device)"
            shaping_pref="$(client_policy_filter_pref "$client_mac")"
            backup_file="$(backup_config firewall "$command_id" "$command_type" || true)"
            if { [ "$download_kbps" -gt 0 ] || [ "$upload_kbps" -gt 0 ]; } && ! traffic_control_healthy; then
                status="failed"; result="$(command_failed_result "client speed limits require tc-full, kmod-sched-flower and kmod-sched-act-police" "dependency_missing" true)"
            elif [ -z "$backup_file" ]; then
                status="failed"; result="$(command_failed_result "failed to create firewall backup")"
            else
                client_policy_clear_firewall_rules "$client_mac"
                if [ "$client_blocked" = "true" ]; then
                    client_policy_set_reject_rule "$client_ref" "$client_mac" "WrtMonitor block $client_mac"
                elif [ "$schedule_enabled" = "true" ]; then
                    blocked_days="$(client_policy_complement_weekdays "$schedule_days")"
                    if client_policy_time_before "$schedule_start" "$schedule_stop"; then
                        [ "$schedule_start" = "00:00" ] \
                            || client_policy_set_reject_rule "$client_ref" "$client_mac" "WrtMonitor before access $client_mac" "$schedule_days" "00:00" "$schedule_start"
                        [ "$schedule_stop" = "23:59" ] \
                            || client_policy_set_reject_rule "$client_after_ref" "$client_mac" "WrtMonitor after access $client_mac" "$schedule_days" "$schedule_stop" "23:59"
                    else
                        client_policy_set_reject_rule "$client_ref" "$client_mac" "WrtMonitor outside overnight access $client_mac" "$schedule_days" "$schedule_stop" "$schedule_start"
                    fi
                    [ -z "$blocked_days" ] \
                        || client_policy_set_reject_rule "$client_days_ref" "$client_mac" "WrtMonitor outside access days $client_mac" "$blocked_days"
                fi
                if [ "$qos_priority" != "normal" ]; then
                    case "$qos_priority" in low) policy_mark="0x10" ;; high) policy_mark="0x30" ;; realtime) policy_mark="0x40" ;; *) policy_mark="0x20" ;; esac
                    uci set "firewall.$qos_ref=rule"
                    uci set "firewall.$qos_ref.name=WrtMonitor priority $client_mac"
                    uci set "firewall.$qos_ref.src=lan"
                    uci set "firewall.$qos_ref.src_mac=$client_mac"
                    uci set "firewall.$qos_ref.target=MARK"
                    uci set "firewall.$qos_ref.set_mark=$policy_mark"
                fi
                case "$dns_provider" in
                    cloudflare-security) policy_dns="1.1.1.2" ;;
                    cloudflare-family) policy_dns="1.1.1.3" ;;
                    none|"") policy_dns="" ;;
                    *) status="failed"; result="$(command_failed_result "unsupported client DNS policy")" ;;
                esac
                if [ "$status" = "done" ] && [ -n "$policy_dns" ]; then
                    uci set "firewall.$dns_ref=redirect"
                    uci set "firewall.$dns_ref.name=WrtMonitor DNS policy $client_mac"
                    uci set "firewall.$dns_ref.src=lan"
                    uci set "firewall.$dns_ref.src_mac=$client_mac"
                    uci set "firewall.$dns_ref.proto=tcp udp"
                    uci set "firewall.$dns_ref.src_dport=53"
                    uci set "firewall.$dns_ref.dest_ip=$policy_dns"
                    uci set "firewall.$dns_ref.dest_port=53"
                    uci set "firewall.$dns_ref.target=DNAT"
                    uci set "firewall.$dot_ref=rule"
                    uci set "firewall.$dot_ref.name=WrtMonitor block DoT $client_mac"
                    uci set "firewall.$dot_ref.src=lan"
                    uci set "firewall.$dot_ref.dest=wan"
                    uci set "firewall.$dot_ref.src_mac=$client_mac"
                    uci set "firewall.$dot_ref.proto=tcp udp"
                    uci set "firewall.$dot_ref.dest_port=853"
                    uci set "firewall.$dot_ref.target=REJECT"
                fi
                if [ "$status" = "done" ] \
                    && client_policy_save_state "$client_mac" "$client_blocked" "$schedule_enabled" "$schedule_days" "$schedule_start" "$schedule_stop" "$qos_priority" "$download_kbps" "$upload_kbps" "$dns_provider" "$shaping_device" "$shaping_pref" \
                    && uci commit firewall \
                    && uci commit wrtmonitor \
                    && service_action firewall reload 20 >/dev/null 2>&1 \
                    && client_policy_apply_runtime_limits "$client_mac" "$download_kbps" "$upload_kbps" "$shaping_device" "$shaping_pref"; then
                    observed="$(client_policy_observed_json "$client_mac")"
                    result="$(command_success_result "client policy applied" "\"backup\":\"$(json_escape "$backup_file")\",\"observed\":$observed")"
                else
                    status="failed"; result="$(command_failed_result "client policy could not be applied or verified" "post_condition_failed")"
                fi
            fi
            ;;
        qos.set_sqm)
            payload_file="/tmp/wrtmonitor-command-payload"; printf '%s' "$command_payload" >"$payload_file"
            sqm_enabled="$(json_get_bool "$payload_file" '@.enabled')"
            sqm_interface="$(json_get_string "$payload_file" '@.interface')"
            sqm_download="$(json_get_number "$payload_file" '@.download_kbps')"
            sqm_upload="$(json_get_number "$payload_file" '@.upload_kbps')"
            sqm_qdisc="$(json_get_string "$payload_file" '@.qdisc')"
            sqm_script="$(json_get_string "$payload_file" '@.script')"
            sqm_profile="$(json_get_string "$payload_file" '@.profile')"
            sqm_qdisc_options="$(json_get_string "$payload_file" '@.qdisc_options')"
            sqm_schedule_enabled="$(json_get_bool "$payload_file" '@.schedule.enabled')"
            sqm_schedule_days="$(jsonfilter -i "$payload_file" -e '@.schedule.weekdays[*]' 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
            sqm_schedule_start="$(json_get_string "$payload_file" '@.schedule.start')"
            sqm_schedule_stop="$(json_get_string "$payload_file" '@.schedule.stop')"
            rm -f "$payload_file"
            [ -n "$sqm_qdisc" ] || sqm_qdisc="cake"
            [ -n "$sqm_script" ] || sqm_script="piece_of_cake.qos"
            sqm_backup="$(backup_config sqm "$command_id" "$command_type" || true)"
            if [ -z "$sqm_backup" ]; then
                status="failed"; result="$(command_failed_result "failed to create SQM backup")"
            elif uci set sqm.wrtmonitor=queue \
                && uci set "sqm.wrtmonitor.enabled=$( [ "$sqm_enabled" = "true" ] && printf 1 || printf 0 )" \
                && uci set "sqm.wrtmonitor.interface=$sqm_interface" \
                && uci set "sqm.wrtmonitor.download=$sqm_download" \
                && uci set "sqm.wrtmonitor.upload=$sqm_upload" \
                && uci set "sqm.wrtmonitor.qdisc=$sqm_qdisc" \
                && uci set "sqm.wrtmonitor.script=$sqm_script" \
                && uci set "sqm.wrtmonitor.qdisc_advanced=$( [ -n "$sqm_qdisc_options" ] && printf 1 || printf 0 )" \
                && uci set "sqm.wrtmonitor.qdisc_really_really_advanced=$( [ -n "$sqm_qdisc_options" ] && printf 1 || printf 0 )" \
                && uci set "sqm.wrtmonitor.eqdisc_opts=$sqm_qdisc_options" \
                  && uci set "sqm.wrtmonitor.iqdisc_opts=$sqm_qdisc_options" \
                  && uci commit sqm \
                  && service_action sqm restart 20 >/dev/null 2>&1; then
                sqm_crontab="${WRTMONITOR_SYSTEM_ROOT:-}/etc/crontabs/root"
                mkdir -p "$(dirname "$sqm_crontab")"
                touch "$sqm_crontab"
                sed -i '/# wrtmonitor-sqm-schedule$/d' "$sqm_crontab"
                if [ "$sqm_schedule_enabled" = true ]; then
                    sqm_cron_days=""
                    for sqm_day in $sqm_schedule_days; do
                        case "$sqm_day" in mon) sqm_number=1 ;; tue) sqm_number=2 ;; wed) sqm_number=3 ;; thu) sqm_number=4 ;; fri) sqm_number=5 ;; sat) sqm_number=6 ;; sun) sqm_number=0 ;; *) continue ;; esac
                        sqm_cron_days="${sqm_cron_days:+$sqm_cron_days,}$sqm_number"
                    done
                    sqm_start_hour="${sqm_schedule_start%:*}"; sqm_start_minute="${sqm_schedule_start#*:}"
                    sqm_stop_hour="${sqm_schedule_stop%:*}"; sqm_stop_minute="${sqm_schedule_stop#*:}"
                    printf '%s %s * * %s /etc/init.d/sqm start # wrtmonitor-sqm-schedule\n' "$sqm_start_minute" "$sqm_start_hour" "$sqm_cron_days" >>"$sqm_crontab"
                    printf '%s %s * * %s /etc/init.d/sqm stop # wrtmonitor-sqm-schedule\n' "$sqm_stop_minute" "$sqm_stop_hour" "$sqm_cron_days" >>"$sqm_crontab"
                fi
                [ ! -x /etc/init.d/cron ] || service_action cron restart 20 >/dev/null 2>&1 || true
                result="$(command_success_result "SQM configuration applied" "\"backup\":\"$(json_escape "$sqm_backup")\",\"profile\":\"$(json_escape "$sqm_profile")\",\"interface\":\"$(json_escape "$sqm_interface")\",\"download_kbps\":$sqm_download,\"upload_kbps\":$sqm_upload")"
            else
                status="failed"; result="$(command_failed_result "failed to apply SQM configuration")"
            fi
            ;;
        *) return 1 ;;
    esac
    return 0
}
