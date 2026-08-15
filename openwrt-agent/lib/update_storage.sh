# shellcheck disable=SC2034

prepare_backup() {
    new_version="$1"
    active_lib_dir="$LIB_INSTALL_DIR"
    current_release="$(release_directory_from_pointer "$RELEASES_DIR/current" 2>/dev/null || true)"
    if [ -r "$current_release/agent-version.txt" ] \
        && [ "$(tr -d '\r\n' <"$current_release/agent-version.txt")" = "$AGENT_VERSION" ]; then
        active_lib_dir="$current_release"
    fi
    ensure_state_dirs
    rm -rf "$BACKUP_DIR/lib.previous"
    mkdir -p "$BACKUP_DIR/lib.previous" || return 1
    cp "$AGENT_INSTALL_PATH" "$BACKUP_DIR/wrtmonitor-agent.previous" || return 1
    cp "$INIT_INSTALL_PATH" "$BACKUP_DIR/wrtmonitor.init.previous" || return 1
    if [ -d "$active_lib_dir" ]; then
        cp "$active_lib_dir"/*.sh "$BACKUP_DIR/lib.previous/" 2>/dev/null || return 1
    fi
    [ -r "$BACKUP_DIR/lib.previous/common.sh" ] || return 1
    printf '%s\n' "$AGENT_VERSION" >"$BACKUP_DIR/VERSION.previous" || return 1
    {
        printf 'created_at=%s\n' "$(iso_now)"
        printf 'previous_version=%s\n' "$AGENT_VERSION"
        printf 'new_version=%s\n' "$new_version"
        printf 'active_lib_dir=%s\n' "$active_lib_dir"
        printf 'reason=pre-update-backup\n'
    } >"$BACKUP_DIR/backup-info.txt" || return 1
}

restore_backup_files() {
    backup_available || return 1
    sh -n "$BACKUP_DIR/wrtmonitor-agent.previous"
    sh -n "$BACKUP_DIR/wrtmonitor.init.previous"
    for path in "$BACKUP_DIR"/lib.previous/*.sh; do
        [ -e "$path" ] || return 1
        sh -n "$path"
    done
    previous_version="$(tr -d '\r\n' <"$BACKUP_DIR/VERSION.previous")"
    rollback_generation="$RELEASES_DIR/${previous_version}-rollback-$(date +%s 2>/dev/null || echo $$)"
    mkdir -p "$rollback_generation"
    cp "$BACKUP_DIR"/lib.previous/*.sh "$rollback_generation"/
    chmod 0755 "$rollback_generation"/*.sh
    printf '%s\n' "$previous_version" >"$rollback_generation/agent-version.txt"

    rollback_generation_id="$(basename "$rollback_generation")"
    atomic_pointer "$rollback_generation_id" "$RELEASES_DIR/version-$previous_version"
    cp "$BACKUP_DIR/wrtmonitor.init.previous" "$INIT_INSTALL_PATH.new"
    chmod 0755 "$INIT_INSTALL_PATH.new"
    cp "$BACKUP_DIR/wrtmonitor-agent.previous" "$AGENT_INSTALL_PATH.new"
    chmod 0755 "$AGENT_INSTALL_PATH.new"

    # Legacy libraries remain a safe fallback for pre-generational entrypoints.
    mkdir -p "$LIB_INSTALL_DIR"
    rm -f "$LIB_INSTALL_DIR"/*.sh
    cp "$BACKUP_DIR"/lib.previous/*.sh "$LIB_INSTALL_DIR"/
    chmod 0755 "$LIB_INSTALL_DIR"/*.sh
    mv "$INIT_INSTALL_PATH.new" "$INIT_INSTALL_PATH"
    mv "$AGENT_INSTALL_PATH.new" "$AGENT_INSTALL_PATH"
    atomic_pointer "$rollback_generation_id" "$RELEASES_DIR/current"
}

manifest_entries() {
    manifest_file="$1"
    sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$manifest_file"
}

directory_is_writable() {
    directory="$1"
    probe="$directory/.wrtmonitor-write-test.$$"
    [ -d "$directory" ] || return 1
    : >"$probe" 2>/dev/null || return 1
    rm -f "$probe"
}

payload_size_kb() {
    du -sk "$1" 2>/dev/null | awk 'NR == 1 { print $1 }'
}

available_space_kb() {
    df -Pk "$1" 2>/dev/null | awk 'NR == 2 { print $4 }'
}

preflight_downloaded_files() {
    tmp_dir="$1"
    INSTALL_PREFLIGHT_ERROR=""
    for directory in "$(dirname "$AGENT_INSTALL_PATH")" "$(dirname "$INIT_INSTALL_PATH")" "$LIB_INSTALL_DIR" "$STATUS_DIR"; do
        if ! directory_is_writable "$directory"; then
            INSTALL_PREFLIGHT_ERROR="filesystem is read-only or not writable: $directory"
            return 1
        fi
    done
    required_kb="$(payload_size_kb "$tmp_dir")"
    available_kb="$(available_space_kb "$LIB_INSTALL_DIR")"
    case "$required_kb:$available_kb" in
        *[!0-9:]*|:*|*:) INSTALL_PREFLIGHT_ERROR="cannot determine free disk space"; return 1 ;;
    esac
    # Staging and rollback keep two complete copies plus filesystem overhead.
    required_kb=$((required_kb * 3 + 512))
    if [ "$available_kb" -lt "$required_kb" ]; then
        INSTALL_PREFLIGHT_ERROR="not enough free space: ${available_kb} KB available, ${required_kb} KB required"
        return 1
    fi
    return 0
}

atomic_pointer() {
    generation_id="$1"
    pointer_path="$2"
    mkdir -p "$(dirname "$pointer_path")"
    printf '%s\n' "$generation_id" >"$pointer_path.new" || return 1
    mv -f "$pointer_path.new" "$pointer_path"
}

release_directory_from_pointer() {
    pointer_path="$1"
    [ -r "$pointer_path" ] || return 1
    generation_id="$(head -n 1 "$pointer_path" 2>/dev/null || true)"
    case "$generation_id" in
        ""|*[!A-Za-z0-9._-]*) return 1 ;;
    esac
    directory="$RELEASES_DIR/$generation_id"
    [ -d "$directory" ] || return 1
    printf '%s' "$directory"
}

manifest_generation_id() {
    version="$1"
    digest="$(sha256sum "$2/SHA256SUMS.txt" | awk '{print substr($1, 1, 12)}')"
    printf '%s-%s' "$version" "$digest"
}

prune_release_generations() {
    keep_current="$(head -n 1 "$RELEASES_DIR/current" 2>/dev/null || true)"
    keep_previous="$(head -n 1 "$RELEASES_DIR/version-$AGENT_VERSION" 2>/dev/null || true)"
    for path in "$RELEASES_DIR"/*; do
        [ -d "$path" ] || continue
        name="$(basename "$path")"
        [ "$name" = "$keep_current" ] && continue
        [ -n "$keep_previous" ] && [ "$name" = "$keep_previous" ] && continue
        rm -rf "$path" 2>/dev/null || true
    done
}

apply_downloaded_files() {
    tmp_dir="$1"
    new_version="$(remote_version_from_tmp "$tmp_dir")"
    generation_id="$(manifest_generation_id "$new_version" "$tmp_dir")"
    generation_tmp="$RELEASES_DIR/.${generation_id}.$$"
    generation="$RELEASES_DIR/$generation_id"
    rm -rf "$generation_tmp"
    mkdir -p "$generation_tmp" || return 1
    for path in "$tmp_dir"/lib/*.sh; do
        [ -e "$path" ] || return 1
        name="$(basename "$path")"
        cp "$path" "$generation_tmp/$name" || return 1
        chmod 0755 "$generation_tmp/$name" || return 1
        sh -n "$generation_tmp/$name" || return 1
    done
    printf '%s\n' "$new_version" >"$generation_tmp/agent-version.txt" || return 1
    if [ -d "$generation" ]; then
        rm -rf "$generation_tmp"
    else
        mv "$generation_tmp" "$generation" || return 1
    fi

    atomic_pointer "$generation_id" "$RELEASES_DIR/version-$new_version" || return 1

    cp "$tmp_dir/wrtmonitor.init" "$INIT_INSTALL_PATH.new" || return 1
    chmod 0755 "$INIT_INSTALL_PATH.new" || return 1
    cp "$tmp_dir/wrtmonitor-agent" "$AGENT_INSTALL_PATH.new" || return 1
    chmod 0755 "$AGENT_INSTALL_PATH.new" || return 1

    # The old entrypoint rejects a current pointer with another version and
    # falls back to its own version alias. The executable is switched last.
    atomic_pointer "$generation_id" "$RELEASES_DIR/current" || return 1
    mv "$INIT_INSTALL_PATH.new" "$INIT_INSTALL_PATH" || return 1
    mv "$AGENT_INSTALL_PATH.new" "$AGENT_INSTALL_PATH" || return 1
}
