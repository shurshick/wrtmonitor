# shellcheck disable=SC2034
find_wifi_schedule() {
    requested_radio="$1"
    schedule_index=0
    while uci -q get "wrtmonitor.@wifi_schedule[$schedule_index]" >/dev/null 2>&1; do
        if [ "$(uci -q get "wrtmonitor.@wifi_schedule[$schedule_index].radio" 2>/dev/null || true)" = "$requested_radio" ]; then
            printf '@wifi_schedule[%s]' "$schedule_index"
            return 0
        fi
        schedule_index=$((schedule_index + 1))
    done
    return 1
}

wifi_time_minutes() {
    value="$1"
    hour="${value%:*}"; minute="${value#*:}"
    hour="${hour#0}"; minute="${minute#0}"
    [ -n "$hour" ] || hour=0
    [ -n "$minute" ] || minute=0
    printf '%s' $((hour * 60 + minute))
}

wifi_day_name() {
    case "$1" in 1) printf mon ;; 2) printf tue ;; 3) printf wed ;; 4) printf thu ;; 5) printf fri ;; 6) printf sat ;; *) printf sun ;; esac
}

wifi_schedule_has_day() {
    case " $1 " in *" $2 "*) return 0 ;; *) return 1 ;; esac
}

wifi_schedule_active_now() {
    days="$1"; start="$2"; stop="$3"
    day_number="$(date +%u 2>/dev/null || echo 1)"
    now_minutes="$(wifi_time_minutes "$(date +%H:%M 2>/dev/null || echo 00:00)")"
    start_minutes="$(wifi_time_minutes "$start")"
    stop_minutes="$(wifi_time_minutes "$stop")"
    today="$(wifi_day_name "$day_number")"
    previous_number=$((day_number - 1)); [ "$previous_number" -gt 0 ] || previous_number=7
    previous="$(wifi_day_name "$previous_number")"
    if [ "$start_minutes" -lt "$stop_minutes" ]; then
        wifi_schedule_has_day "$days" "$today" && [ "$now_minutes" -ge "$start_minutes" ] && [ "$now_minutes" -lt "$stop_minutes" ]
    else
        { wifi_schedule_has_day "$days" "$today" && [ "$now_minutes" -ge "$start_minutes" ]; } \
            || { wifi_schedule_has_day "$days" "$previous" && [ "$now_minutes" -lt "$stop_minutes" ]; }
    fi
}

wifi_schedule_base_enabled() {
    schedule_ref="$1"; schedule_radio="$2"
    base_enabled="$(uci -q get "wrtmonitor.$schedule_ref.base_enabled" 2>/dev/null || true)"
    case "$base_enabled" in 0|1) printf '%s' "$base_enabled" ;; *)
        current_disabled="$(uci -q get "wireless.$schedule_radio.disabled" 2>/dev/null || echo 0)"
        [ "$current_disabled" = 1 ] && printf 0 || printf 1
        ;;
    esac
}

apply_wifi_schedules() {
    schedule_index=0; wireless_changed=0; schedule_changed=0
    while uci -q get "wrtmonitor.@wifi_schedule[$schedule_index]" >/dev/null 2>&1; do
        schedule_ref="@wifi_schedule[$schedule_index]"
        schedule_enabled="$(uci -q get "wrtmonitor.$schedule_ref.enabled" 2>/dev/null || echo 0)"
        schedule_radio="$(uci -q get "wrtmonitor.$schedule_ref.radio" 2>/dev/null || true)"
        schedule_days="$(uci -q get "wrtmonitor.$schedule_ref.weekdays" 2>/dev/null || true)"
        schedule_start="$(uci -q get "wrtmonitor.$schedule_ref.start" 2>/dev/null || true)"
        schedule_stop="$(uci -q get "wrtmonitor.$schedule_ref.stop" 2>/dev/null || true)"
        [ -n "$schedule_radio" ] || { schedule_index=$((schedule_index + 1)); continue; }
        base_enabled="$(wifi_schedule_base_enabled "$schedule_ref" "$schedule_radio")"
        applied="$(uci -q get "wrtmonitor.$schedule_ref.applied" 2>/dev/null || echo 0)"
        if [ "$schedule_enabled" = 1 ] && [ -n "$schedule_start" ] && [ -n "$schedule_stop" ]; then
            if ! uci -q get "wrtmonitor.$schedule_ref.base_enabled" >/dev/null 2>&1; then
                # Older agents changed wireless.disabled directly. An enabled legacy schedule
                # therefore means the owner's intended state was enabled.
                base_enabled=1
                uci set "wrtmonitor.$schedule_ref.base_enabled=1"
                schedule_changed=1
            fi
            desired_disabled=1
            [ "$base_enabled" = 1 ] && wifi_schedule_active_now "$schedule_days" "$schedule_start" "$schedule_stop" && desired_disabled=0
            [ "$applied" = 1 ] || { uci set "wrtmonitor.$schedule_ref.applied=1"; schedule_changed=1; }
        else
            desired_disabled="$( [ "$base_enabled" = 1 ] && printf 0 || printf 1 )"
            if [ "$applied" = 1 ]; then
                uci set "wrtmonitor.$schedule_ref.applied=0"
                schedule_changed=1
            fi
        fi
        current_disabled="$(uci -q get "wireless.$schedule_radio.disabled" 2>/dev/null || echo 0)"
        if [ "$current_disabled" != "$desired_disabled" ]; then
            uci set "wireless.$schedule_radio.disabled=$desired_disabled"
            wireless_changed=1
        fi
        schedule_index=$((schedule_index + 1))
    done
    [ "$schedule_changed" = 0 ] || uci commit wrtmonitor
    if [ "$wireless_changed" = 1 ]; then
        uci commit wireless && wifi reload >/dev/null 2>&1
    fi
}
