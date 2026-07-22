DEFAULT_UPDATE_INTERVAL_HOURS="6"

parse_version_parts() {
    normalized="$(printf '%s' "$1" | sed 's/^v//; s/+.*$//')"
    base="${normalized%%-*}"
    prerelease=""
    [ "$base" = "$normalized" ] || prerelease="${normalized#*-}"
    old_ifs="$IFS"
    IFS=.
    # shellcheck disable=SC2086
    set -- $base
    IFS="$old_ifs"
    [ "$#" -eq 3 ] || return 1
    major="$1"
    minor="$2"
    patch="$3"
    for part in "$major" "$minor" "$patch"; do
        case "$part" in ""|*[!0-9]*) return 1 ;; esac
    done
    case "$prerelease" in
        "") stable_rank=1; rc_number=0 ;;
        rc[0-9]*)
            rc_number="${prerelease#rc}"
            case "$rc_number" in ""|*[!0-9]*) return 1 ;; esac
            stable_rank=0
            ;;
        *) return 1 ;;
    esac
    printf '%s %s %s %s %s' "$major" "$minor" "$patch" "$stable_rank" "$rc_number"
}

compare_versions() {
    left="$(parse_version_parts "$1")"
    right="$(parse_version_parts "$2")"
    if [ -z "$left" ] || [ -z "$right" ]; then
        awk -v left_raw="$1" -v right_raw="$2" 'BEGIN {
            if (left_raw == right_raw) {
                print 0
            } else if (left_raw > right_raw) {
                print 1
            } else {
                print -1
            }
        }'
        return
    fi
    # shellcheck disable=SC2086
    set -- $left
    left_major="$1"
    left_minor="$2"
    left_patch="$3"
    left_stable="$4"
    left_rc="$5"
    # shellcheck disable=SC2086
    set -- $right
    right_major="$1"
    right_minor="$2"
    right_patch="$3"
    right_stable="$4"
    right_rc="$5"
    if [ "$left_major" -gt "$right_major" ]; then printf '1'; return; fi
    if [ "$left_major" -lt "$right_major" ]; then printf '%s' '-1'; return; fi
    if [ "$left_minor" -gt "$right_minor" ]; then printf '1'; return; fi
    if [ "$left_minor" -lt "$right_minor" ]; then printf '%s' '-1'; return; fi
    if [ "$left_patch" -gt "$right_patch" ]; then printf '1'; return; fi
    if [ "$left_patch" -lt "$right_patch" ]; then printf '%s' '-1'; return; fi
    if [ "$left_stable" -gt "$right_stable" ]; then printf '1'; return; fi
    if [ "$left_stable" -lt "$right_stable" ]; then printf '%s' '-1'; return; fi
    if [ "$left_rc" -gt "$right_rc" ]; then printf '1'; return; fi
    if [ "$left_rc" -lt "$right_rc" ]; then printf '%s' '-1'; return; fi
    printf '0'
}

update_interval_seconds() {
    hours="$(cfg update_interval_hours)"
    case "$hours" in
        ""|*[!0-9]*) hours="$DEFAULT_UPDATE_INTERVAL_HOURS" ;;
    esac
    if [ "$hours" -le 0 ]; then
        hours="$DEFAULT_UPDATE_INTERVAL_HOURS"
    fi
    printf '%s' $((hours * 3600))
}

download_file() {
    url="$1"
    destination="$2"
    curl -fsS --connect-timeout 10 --max-time 60 -o "$destination" "$url"
}

checksum_for() {
    sha256sum "$1" | awk '{print $1}'
}

checksum_expected_for() {
    sums_file="$1"
    filename="$2"
    awk -v name="$filename" '$2 == name {print $1}' "$sums_file" | head -n 1
}

verify_checksum() {
    sums_file="$1"
    file_path="$2"
    filename="$3"
    expected="$(checksum_expected_for "$sums_file" "$filename")"
    if [ -z "$expected" ]; then
        return 1
    fi
    actual="$(checksum_for "$file_path")"
    [ "$actual" = "$expected" ]
}

remote_version_from_tmp() {
    tr -d '\r\n' <"$1/agent-version.txt"
}

prepare_backup() {
    new_version="$1"
    ensure_state_dirs
    rm -rf "$BACKUP_DIR/lib.previous"
    mkdir -p "$BACKUP_DIR/lib.previous"
    cp /usr/bin/wrtmonitor-agent "$BACKUP_DIR/wrtmonitor-agent.previous"
    cp /etc/init.d/wrtmonitor "$BACKUP_DIR/wrtmonitor.init.previous"
    if [ -d "$LIB_INSTALL_DIR" ]; then
        cp "$LIB_INSTALL_DIR"/*.sh "$BACKUP_DIR/lib.previous/" 2>/dev/null || true
    fi
    printf '%s\n' "$AGENT_VERSION" >"$BACKUP_DIR/VERSION.previous"
    {
        printf 'created_at=%s\n' "$(iso_now)"
        printf 'previous_version=%s\n' "$AGENT_VERSION"
        printf 'new_version=%s\n' "$new_version"
        printf 'reason=pre-update-backup\n'
    } >"$BACKUP_DIR/backup-info.txt"
}

restore_backup_files() {
    backup_available || return 1
    sh -n "$BACKUP_DIR/wrtmonitor-agent.previous"
    sh -n "$BACKUP_DIR/wrtmonitor.init.previous"
    for path in "$BACKUP_DIR"/lib.previous/*.sh; do
        [ -e "$path" ] || return 1
        sh -n "$path"
    done
    cp "$BACKUP_DIR/wrtmonitor-agent.previous" /usr/bin/wrtmonitor-agent
    chmod 0755 /usr/bin/wrtmonitor-agent
    cp "$BACKUP_DIR/wrtmonitor.init.previous" /etc/init.d/wrtmonitor
    chmod 0755 /etc/init.d/wrtmonitor
    mkdir -p "$LIB_INSTALL_DIR"
    rm -f "$LIB_INSTALL_DIR"/*.sh
    cp "$BACKUP_DIR"/lib.previous/*.sh "$LIB_INSTALL_DIR"/
    chmod 0755 "$LIB_INSTALL_DIR"/*.sh
}

manifest_entries() {
    manifest_file="$1"
    sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$manifest_file"
}

apply_downloaded_files() {
    tmp_dir="$1"
    cp "$tmp_dir/wrtmonitor-agent" /usr/bin/wrtmonitor-agent.new
    chmod 0755 /usr/bin/wrtmonitor-agent.new
    mv /usr/bin/wrtmonitor-agent.new /usr/bin/wrtmonitor-agent

    cp "$tmp_dir/wrtmonitor.init" /etc/init.d/wrtmonitor.new
    chmod 0755 /etc/init.d/wrtmonitor.new
    mv /etc/init.d/wrtmonitor.new /etc/init.d/wrtmonitor

    mkdir -p "$LIB_INSTALL_DIR"
    rm -f "$LIB_INSTALL_DIR"/*.sh
    for path in "$tmp_dir"/lib/*.sh; do
        [ -e "$path" ] || continue
        name="$(basename "$path")"
        cp "$path" "$LIB_INSTALL_DIR/$name"
        chmod 0755 "$LIB_INSTALL_DIR/$name"
    done
}

validate_download_set() {
    tmp_dir="$1"
    manifest="$tmp_dir/openwrt-agent-files.txt"
    sums="$tmp_dir/SHA256SUMS.txt"
    [ -r "$manifest" ] || return 1
    [ -r "$sums" ] || return 1

    for filename in $(manifest_entries "$manifest"); do
        [ "$filename" = "SHA256SUMS.txt" ] && continue
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
    for filename in $(manifest_entries "$tmp_dir/openwrt-agent-files.txt"); do
        [ "$filename" = "SHA256SUMS.txt" ] && continue
        target="$tmp_dir/$filename"
        target_dir="$(dirname "$target")"
        mkdir -p "$target_dir"
        download_file "$base/$filename" "$target"
    done
}

verify_installed_agent() {
    expected="$1"
    installed_version="$(/usr/bin/wrtmonitor-agent version 2>/dev/null || true)"
    [ -n "$installed_version" ] && [ "$installed_version" = "$expected" ]
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

check_for_update() {
    mode="$1"
    force="${2:-0}"
    allow_downgrade="${3:-0}"
    if [ "$mode" = "scheduled" ] && ! auto_update_enabled; then
        return 0
    fi
    acquire_update_lock || return 0
    tmp_dir="/tmp/wrtmonitor-update.$$"
    rm -rf "$tmp_dir"
    mkdir -p "$tmp_dir"
    if ! stage_update_downloads "$tmp_dir"; then
        remember_update_result "failed" "download failed" ""
        log_notice "agent update failed: download failed"
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    remote_version="$(remote_version_from_tmp "$tmp_dir")"
    if ! validate_download_set "$tmp_dir"; then
        remember_update_result "failed" "checksum or syntax verification failed" "$remote_version"
        log_notice "agent update failed: checksum or syntax verification failed"
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    comparison="$(compare_versions "$AGENT_VERSION" "$remote_version")"
    if [ "$comparison" = "0" ] && [ "$force" != "1" ]; then
        remember_update_result "skipped" "" "$remote_version"
        rm -rf "$tmp_dir"
        release_update_lock
        return 0
    fi
    if [ "$comparison" = "1" ] && [ "$allow_downgrade" != "1" ] && ! allow_downgrade_enabled; then
        remember_update_result "skipped" "downgrade blocked" "$remote_version"
        log_notice "agent update skipped: downgrade blocked"
        rm -rf "$tmp_dir"
        release_update_lock
        return 0
    fi
    if ! prepare_backup "$remote_version"; then
        remember_update_result "failed" "backup failed" "$remote_version"
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    if ! apply_downloaded_files "$tmp_dir"; then
        perform_rollback "internal" "install failed" || true
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    if ! /usr/bin/wrtmonitor-agent ensure-dependencies; then
        perform_rollback "internal" "required dependency installation failed" || true
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    if ! verify_installed_agent "$remote_version"; then
        perform_rollback "internal" "installed agent validation failed" || true
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
    fi
    remember_update_result "success" "" "$remote_version"
    log_notice "agent updated: $AGENT_VERSION -> $remote_version"
    PENDING_AGENT_EXEC=1
    rm -rf "$tmp_dir"
    release_update_lock
    if [ "$mode" = "manual" ]; then
        if ! restart_service_foreground; then
            perform_rollback "manual" "service restart failed" || true
            return 1
        fi
        # shellcheck disable=SC2034
        PENDING_AGENT_EXEC=0
    fi
    return 0
}

manual_update() {
    force="0"
    allow_downgrade="0"
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --force) force="1" ;;
            --allow-downgrade) allow_downgrade="1" ;;
            *) echo "Unknown update flag: $1" >&2; exit 1 ;;
        esac
        shift
    done
    check_for_update "manual" "$force" "$allow_downgrade"
}

manual_rollback() {
    perform_rollback "manual" "manual rollback"
}
