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

if [ -z "$SERVER_URL" ] || [ -z "$DEVICE_TOKEN" ]; then
  echo "Usage: sh install-openwrt.sh --server https://monitor.example.ru --token DEVICE_TOKEN [--name Router]" >&2
  exit 1
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
