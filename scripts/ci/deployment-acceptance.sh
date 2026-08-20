#!/bin/sh
set -eu

OLD_IMAGE="$1"
NEW_IMAGE="$2"
NETWORK="wrtmonitor-acceptance-$$"
POSTGRES="wrtmonitor-postgres-$$"
APP="wrtmonitor-app-$$"
VOLUME="wrtmonitor-postgres-acceptance-$$"
STATE="/tmp/wrtmonitor-deployment-state-$$.json"
DB_PASSWORD="deployment-acceptance-password"
JWT_SECRET="deployment-acceptance-jwt-secret-with-more-than-32-characters"

cleanup() {
  docker rm -f "$APP" "$POSTGRES" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
  docker volume rm "$VOLUME" >/dev/null 2>&1 || true
  rm -f "$STATE"
}
trap cleanup EXIT

docker network create "$NETWORK" >/dev/null
docker volume create "$VOLUME" >/dev/null
docker run -d --name "$POSTGRES" --network "$NETWORK" \
  -v "$VOLUME:/var/lib/postgresql/data" \
  -e POSTGRES_DB=wrtmonitor \
  -e POSTGRES_USER=wrtmonitor \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" \
  postgres:16-alpine >/dev/null

for attempt in $(seq 1 30); do
  if docker exec "$POSTGRES" pg_isready -U wrtmonitor -d wrtmonitor >/dev/null 2>&1; then
    break
  fi
  test "$attempt" -lt 30
  sleep 1
done

start_app() {
  image="$1"
  docker run -d --name "$APP" --network "$NETWORK" -p 18088:8080 \
    -e WRTMONITOR_DATABASE_URL="postgresql+psycopg://wrtmonitor:$DB_PASSWORD@$POSTGRES:5432/wrtmonitor" \
    -e WRTMONITOR_PUBLIC_SERVER_URL=http://127.0.0.1:18088 \
    -e WRTMONITOR_ALLOW_INSECURE_LOCAL=true \
    -e WRTMONITOR_JWT_SECRET="$JWT_SECRET" \
    "$image" >/dev/null
  for attempt in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:18088/ready >/dev/null 2>&1; then
      return
    fi
    test "$attempt" -lt 60
    sleep 1
  done
}

docker pull "$OLD_IMAGE" >/dev/null
start_app "$OLD_IMAGE"
python scripts/deployment_acceptance.py seed \
  --server http://127.0.0.1:18088 \
  --state "$STATE"
docker rm -f "$APP" >/dev/null

start_app "$NEW_IMAGE"
python scripts/deployment_acceptance.py verify \
  --server http://127.0.0.1:18088 \
  --state "$STATE"
docker exec "$APP" python -m backend.app.backup_cli create /tmp/wrtmonitor-upgrade.dump
docker exec "$APP" python -m backend.app.backup_cli verify /tmp/wrtmonitor-upgrade.dump
docker exec "$APP" python -m backend.app.backup_cli drill /tmp/wrtmonitor-upgrade.dump
docker rm -f "$APP" >/dev/null

docker exec "$POSTGRES" createdb -U wrtmonitor wrtmonitor_clean
docker run -d --name "$APP" --network "$NETWORK" -p 18088:8080 \
  -e WRTMONITOR_DATABASE_URL="postgresql+psycopg://wrtmonitor:$DB_PASSWORD@$POSTGRES:5432/wrtmonitor_clean" \
  -e WRTMONITOR_PUBLIC_SERVER_URL=http://127.0.0.1:18088 \
  -e WRTMONITOR_ALLOW_INSECURE_LOCAL=true \
  -e WRTMONITOR_JWT_SECRET="$JWT_SECRET" \
  "$NEW_IMAGE" >/dev/null
for attempt in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:18088/ready >/dev/null 2>&1; then
    break
  fi
  test "$attempt" -lt 60
  sleep 1
done
python scripts/deployment_acceptance.py clean-install --server http://127.0.0.1:18088
