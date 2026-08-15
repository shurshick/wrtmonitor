# shellcheck disable=SC2034

validate_download_set() {
    tmp_dir="$1"
    manifest="$tmp_dir/openwrt-agent-files.txt"
    sums="$tmp_dir/SHA256SUMS.txt"
    [ -r "$manifest" ] || return 1
    [ -r "$sums" ] || return 1
    if [ ! -r "$tmp_dir/SHA256SUMS.sig" ] && [ ! -r "$tmp_dir/SHA256SUMS.rsa.sig" ]; then
        return 1
    fi
    verify_manifest_signature "$tmp_dir" || return 1

    for filename in $(manifest_entries "$manifest"); do
        case "$filename" in SHA256SUMS.txt|SHA256SUMS.sig|SHA256SUMS.rsa.sig) continue ;; esac
        [ -r "$tmp_dir/$filename" ] || return 1
        verify_checksum "$sums" "$tmp_dir/$filename" "$filename" || return 1
    done

    sh -n "$tmp_dir/wrtmonitor-agent"
    sh -n "$tmp_dir/wrtmonitor.init"
    sh -n "$tmp_dir/install-openwrt.sh"
    for path in "$tmp_dir"/lib/*.sh; do
        [ -e "$path" ] || return 1
        sh -n "$path"
    done

    remote_version="$(remote_version_from_tmp "$tmp_dir")"
    [ -n "$remote_version" ] || return 1
    parsed_version="$(sed -n 's/^AGENT_VERSION="\([^"]*\)".*/\1/p' "$tmp_dir/wrtmonitor-agent" | head -n 1)"
    [ -n "$parsed_version" ] && [ "$parsed_version" = "$remote_version" ]
}

stage_update_downloads() {
    tmp_dir="$1"
    mkdir -p "$tmp_dir/lib"
    base="$(update_source)"
    download_file "$base/openwrt-agent-files.txt" "$tmp_dir/openwrt-agent-files.txt"
    download_file "$base/SHA256SUMS.txt" "$tmp_dir/SHA256SUMS.txt"
    download_file "$base/SHA256SUMS.sig" "$tmp_dir/SHA256SUMS.sig" || rm -f "$tmp_dir/SHA256SUMS.sig"
    download_file "$base/SHA256SUMS.rsa.sig" "$tmp_dir/SHA256SUMS.rsa.sig" || rm -f "$tmp_dir/SHA256SUMS.rsa.sig"
    for filename in $(manifest_entries "$tmp_dir/openwrt-agent-files.txt"); do
        case "$filename" in SHA256SUMS.txt|SHA256SUMS.sig|SHA256SUMS.rsa.sig) continue ;; esac
        target="$tmp_dir/$filename"
        target_dir="$(dirname "$target")"
        mkdir -p "$target_dir"
        download_file "$base/$filename" "$target"
    done
}

verify_installed_agent() {
    expected="$1"
    installed_version="$("$AGENT_INSTALL_PATH" version 2>/dev/null || true)"
    installed_release="$(release_directory_from_pointer "$RELEASES_DIR/current" 2>/dev/null || true)"
    [ -n "$installed_version" ] \
        && [ "$installed_version" = "$expected" ] \
        && [ -r "$installed_release/common.sh" ] \
        && [ "$(tr -d '\r\n' <"$installed_release/agent-version.txt")" = "$expected" ]
}

handoff_to_updated_agent() {
    release_run_lock
    exec /usr/bin/wrtmonitor-agent daemon
}

restart_service_foreground() {
    /etc/init.d/wrtmonitor restart >/dev/null 2>&1
}

perform_rollback() {
    mode="$1"
    reason="${2:-manual rollback}"
    if ! restore_backup_files; then
        remember_update_result "failed" "rollback unavailable" "$(load_status; printf '%s' "$AVAILABLE_VERSION")"
        return 1
    fi
    remember_update_result "rollback" "$reason" "$AGENT_VERSION"
    log_notice "agent rollback completed: $reason"
    PENDING_AGENT_EXEC=1
    if [ "$mode" = "manual" ]; then
        restart_service_foreground || return 1
        PENDING_AGENT_EXEC=0
    fi
    return 0
}

acquire_update_lock() {
    now="$(date +%s 2>/dev/null || echo 0)"
    if [ -r "$UPDATE_LOCK_FILE" ]; then
        old_pid="$(awk -F= '/^pid=/{print $2}' "$UPDATE_LOCK_FILE" 2>/dev/null | head -n 1)"
        old_started="$(awk -F= '/^started=/{print $2}' "$UPDATE_LOCK_FILE" 2>/dev/null | head -n 1)"
        age=$((now - ${old_started:-0}))
        if [ -n "${old_pid:-}" ] && kill -0 "$old_pid" 2>/dev/null && [ "$age" -lt "$UPDATE_LOCK_STALE_SECONDS" ]; then
            remember_update_result "skipped" "Update already running" "$(load_status; printf '%s' "$AVAILABLE_VERSION")"
            log_notice "Update already running"
            return 1
        fi
        rm -f "$UPDATE_LOCK_FILE"
    fi
    {
        printf 'pid=%s\n' "$$"
        printf 'started=%s\n' "$now"
    } >"$UPDATE_LOCK_FILE"
}

release_update_lock() {
    rm -f "$UPDATE_LOCK_FILE"
}
