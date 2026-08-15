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
    if ! preflight_downloaded_files "$tmp_dir"; then
        error="${INSTALL_PREFLIGHT_ERROR:-installation preflight failed}"
        remember_update_result "failed" "$error" "$remote_version" || true
        log_notice "agent update failed: $error"
        rm -rf "$tmp_dir"
        release_update_lock
        return 1
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
    prune_release_generations
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
