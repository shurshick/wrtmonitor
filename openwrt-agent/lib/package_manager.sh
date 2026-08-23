package_manager_name() {
    if command -v apk >/dev/null 2>&1; then
        printf 'apk'
    elif command -v opkg >/dev/null 2>&1; then
        printf 'opkg'
    else
        return 1
    fi
}

package_refresh_indexes() {
    case "$(package_manager_name)" in
        apk) apk update ;;
        opkg) opkg update ;;
    esac
}

package_apply() {
    action="$1"
    package="$2"
    case "$(package_manager_name)" in
        apk)
            case "$action" in
                install) apk add "$package" ;;
                remove) apk del "$package" ;;
                upgrade) apk upgrade "$package" ;;
                *) return 1 ;;
            esac
            ;;
        opkg)
            case "$action" in
                install|remove|upgrade) opkg "$action" "$package" ;;
                *) return 1 ;;
            esac
            ;;
    esac
}

package_installed_version() {
    package="$1"
    package_list_installed 2>/dev/null \
        | awk -F'|' -v package="$package" '$1 == package {print $2; exit}'
}

package_upgrade_candidate() {
    package="$1"
    package_list_upgradeable 2>/dev/null \
        | awk -F'|' -v package="$package" '$1 == package {print $3; exit}'
}

package_list_installed() {
    case "$(package_manager_name)" in
        apk) apk list --installed --manifest 2>/dev/null | awk 'NF >= 2 {print $1 "|" $2}' ;;
        opkg) opkg list-installed 2>/dev/null | awk 'NF >= 3 {print $1 "|" $3}' ;;
    esac
}

package_list_upgradeable() {
    case "$(package_manager_name)" in
        apk)
            upgrade_rows="$(
                apk query --upgradable --fields name,version '*' 2>/dev/null \
                    | awk '/^Name: / {name = substr($0, 7); next} /^Version: / && name != "" {print "U|" name "|" substr($0, 10); name = ""}' \
                    || true
            )"
            if [ -z "$upgrade_rows" ]; then
                upgrade_rows="$(apk list --upgradeable --manifest 2>/dev/null | awk 'NF >= 2 {print "U|" $1 "|" $2}')"
            fi
            {
                apk list --installed --manifest 2>/dev/null | awk 'NF >= 2 {print "I|" $1 "|" $2}'
                printf '%s\n' "$upgrade_rows"
            } | awk -F'|' '$1 == "I" {current[$2] = $3; next} $1 == "U" {print $2 "|" current[$2] "|" $3}'
            ;;
        opkg) opkg list-upgradable 2>/dev/null | awk 'NF >= 5 {print $1 "|" $3 "|" $5}' ;;
    esac
}
