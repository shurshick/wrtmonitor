#!/bin/sh
set -eu

SERVER_URL=""
DEVICE_TOKEN=""
NAME=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --server) SERVER_URL="$2"; shift 2 ;;
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

if [ -z "$SERVER_URL" ]; then
  SERVER_URL="$(prompt_value 'wrtmonitor server URL, example https://monitor.example.ru' "$SERVER_URL" 1)"
fi

if [ -z "$DEVICE_TOKEN" ]; then
  DEVICE_TOKEN="$(prompt_value 'Device token' "$DEVICE_TOKEN" 1)"
fi

if [ -z "$NAME" ]; then
  NAME="$(prompt_value 'Router name, optional' "$NAME" 0)"
fi

install -m 0755 wrtmonitor-agent /usr/bin/wrtmonitor-agent
install -m 0755 wrtmonitor.init /etc/init.d/wrtmonitor

uci -q batch <<EOF
set wrtmonitor.main=wrtmonitor
set wrtmonitor.main.enabled='1'
set wrtmonitor.main.server_url='$SERVER_URL'
set wrtmonitor.main.device_token='$DEVICE_TOKEN'
set wrtmonitor.main.name='$NAME'
set wrtmonitor.main.interval='60'
commit wrtmonitor
EOF

/etc/init.d/wrtmonitor enable
/etc/init.d/wrtmonitor restart
echo "wrtmonitor agent installed"
