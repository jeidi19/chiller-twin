#!/usr/bin/env bash
# End-to-end check of the running stack (docker compose up -d --build):
#   1. data flows simulator → OPC UA → gateway → MQTT → collector → InfluxDB;
#   2. Grafana has provisioned the datasource (and it can reach InfluxDB) and the dashboard.
# Usage: scripts/e2e_check.sh [timeout_s]   (reads .env for org, bucket, token, password)
set -euo pipefail

TIMEOUT_S="${1:-180}"
INFLUX_URL="${INFLUX_URL:-http://localhost:8086}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
MIN_POINTS=10

set -a
# shellcheck disable=SC1091
source .env
set +a

count_points() {
  # Number of samples written in the last 10 minutes (all series merged).
  curl -sf "${INFLUX_URL}/api/v2/query?org=${INFLUXDB_ORG}" \
    -H "Authorization: Token ${INFLUXDB_TOKEN}" \
    -H "Accept: application/csv" \
    -H "Content-Type: application/vnd.flux" \
    --data "from(bucket: \"${INFLUXDB_BUCKET}\")
      |> range(start: -10m)
      |> filter(fn: (r) => r._field == \"cell_temp_c\")
      |> group()
      |> count()
      |> keep(columns: [\"_value\"])" \
    | tr -d '\r' | awk -F, '$NF ~ /^[0-9]+$/ { n = $NF } END { print n + 0 }'
}

echo "Waiting for at least ${MIN_POINTS} points in InfluxDB (timeout ${TIMEOUT_S} s)..."
deadline=$((SECONDS + TIMEOUT_S))
points=0
while ((SECONDS < deadline)); do
  points="$(count_points || echo 0)"
  if ((points >= MIN_POINTS)); then
    break
  fi
  sleep 5
done
if ((points < MIN_POINTS)); then
  echo "FAIL: only ${points} points in InfluxDB after ${TIMEOUT_S} s" >&2
  exit 1
fi
echo "OK: ${points} points in InfluxDB"

grafana() {
  curl -sf -u "admin:${GRAFANA_PASSWORD}" "${GRAFANA_URL}$1"
}
grafana /api/datasources/uid/influxdb/health >/dev/null \
  || { echo "FAIL: Grafana datasource 'influxdb' missing or unhealthy" >&2; exit 1; }
echo "OK: Grafana datasource reaches InfluxDB"
grafana /api/dashboards/uid/chiller-twin >/dev/null \
  || { echo "FAIL: Grafana dashboard 'chiller-twin' not provisioned" >&2; exit 1; }
echo "OK: Grafana dashboard provisioned"
