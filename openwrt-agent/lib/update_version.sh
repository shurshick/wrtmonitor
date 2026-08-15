DEFAULT_UPDATE_INTERVAL_HOURS="1"

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
    # Six hours was the historical default. Migrate that value without
    # overriding deliberate custom schedules.
    if [ "$hours" = "6" ]; then
        hours="$DEFAULT_UPDATE_INTERVAL_HOURS"
    fi
    if [ "$hours" -le 0 ]; then
        hours="$DEFAULT_UPDATE_INTERVAL_HOURS"
    fi
    printf '%s' $((hours * 3600))
}
