#!/bin/sh
set -eu

SERVER_URL=""
DEVICE_TOKEN=""
DEVICE_ID=""
NAME=""
ADMIN_USERNAME=""
ADMIN_PASSWORD=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --server) SERVER_URL="$2"; shift 2 ;;
    --admin-user) ADMIN_USERNAME="$2"; shift 2 ;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
    --token) DEVICE_TOKEN="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

prompt_value() {
  label="$1"
  current="$2"
  required="$3"
  while [ -z "$current" ]; do
    printf '%s: ' "$label" >&2
    read -r current
    if [ "$required" != "1" ]; then
      break
    fi
  done
  printf '%s' "$current"
}

prompt_secret() {
  label="$1"
  current="$2"
  if [ -n "$current" ]; then
    printf '%s' "$current"
    return
  fi
  printf '%s: ' "$label" >&2
  if command -v stty >/dev/null 2>&1; then
    stty -echo
    read -r current
    stty echo
    printf '\n' >&2
  else
    read -r current
  fi
  printf '%s' "$current"
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

post_json() {
  path="$1"
  body="$2"
  auth="${3:-}"
  if [ -n "$auth" ]; then
    curl -fsS -X POST "$SERVER_URL$path" -H "Content-Type: application/json" -H "Authorization: Bearer $auth" -d "$body"
  else
    curl -fsS -X POST "$SERVER_URL$path" -H "Content-Type: application/json" -d "$body"
  fi
}

if [ -z "$SERVER_URL" ]; then
  SERVER_URL="$(prompt_value 'wrtmonitor server URL, example https://monitor.example.ru' "$SERVER_URL" 1)"
fi
SERVER_URL="$(printf '%s' "$SERVER_URL" | sed 's#/$##')"

if [ -z "$DEVICE_TOKEN" ]; then
  ADMIN_USERNAME="$(prompt_value 'Administrator username' "$ADMIN_USERNAME" 1)"
  ADMIN_PASSWORD="$(prompt_secret 'Administrator password' "$ADMIN_PASSWORD")"
fi

if [ -z "$NAME" ]; then
  NAME="$(prompt_value 'Router name, optional' "$NAME" 0)"
fi

if [ -z "$DEVICE_TOKEN" ]; then
  hostname_value="$(json_escape "$(uci -q get system.@system[0].hostname 2>/dev/null || hostname)")"
  model_value="$(json_escape "$(cat /tmp/sysinfo/model 2>/dev/null || echo OpenWrt)")"
  firmware_value="$(json_escape "$(cat /etc/openwrt_release 2>/dev/null | grep DISTRIB_DESCRIPTION | cut -d\\' -f2 || echo OpenWrt)")"
  name_value="$(json_escape "$NAME")"
  login_body="{\"username\":\"$(json_escape "$ADMIN_USERNAME")\",\"password\":\"$(json_escape "$ADMIN_PASSWORD")\"}"
  login_response="$(post_json /api/v1/auth/login "$login_body")"
  admin_token="$(printf '%s' "$login_response" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
  [ -n "$admin_token" ] || { echo "Failed to login as administrator" >&2; exit 1; }

  provision_body="{\"hostname\":\"$hostname_value\",\"model\":\"$model_value\",\"firmware\":\"$firmware_value\",\"name\":\"$name_value\"}"
  provision_response="$(post_json /api/v1/devices/provision "$provision_body" "$admin_token")"
  DEVICE_ID="$(printf '%s' "$provision_response" | sed -n 's/.*"device_id":"\([^"]*\)".*/\1/p')"
  DEVICE_TOKEN="$(printf '%s' "$provision_response" | sed -n 's/.*"device_token":"\([^"]*\)".*/\1/p')"
  [ -n "$DEVICE_ID" ] || { echo "Failed to provision device" >&2; exit 1; }
  [ -n "$DEVICE_TOKEN" ] || { echo "Failed to receive device token" >&2; exit 1; }
fi

install -m 0755 wrtmonitor-agent /usr/bin/wrtmonitor-agent
install -m 0755 wrtmonitor.init /etc/init.d/wrtmonitor

uci -q batch <<EOF
set wrtmonitor.main=wrtmonitor
set wrtmonitor.main.enabled='1'
set wrtmonitor.main.server_url='$SERVER_URL'
set wrtmonitor.main.device_token='$DEVICE_TOKEN'
set wrtmonitor.main.device_id='$DEVICE_ID'
set wrtmonitor.main.name='$NAME'
set wrtmonitor.main.interval='60'
commit wrtmonitor
EOF

/etc/init.d/wrtmonitor enable
/etc/init.d/wrtmonitor restart
echo "wrtmonitor agent installed"
