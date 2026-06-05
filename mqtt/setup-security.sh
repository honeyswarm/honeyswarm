#!/usr/bin/env bash
# Generate the MQTT broker's self-signed TLS material and password file.
# Run once before `docker compose up` (re-run to add SANs / rotate certs).
#
# Usage:
#   ./mqtt/setup-security.sh [extra-hostname-or-IP ...]
#
# Always includes SANs: DNS:mqtt, DNS:localhost, IP:127.0.0.1 so both the
# in-network controller (host "mqtt") and a local agent (localhost) verify.
# Pass your controller's public hostname/IP for remote hives, e.g.:
#   ./mqtt/setup-security.sh honeyswarm.example.com 203.0.113.10
#
# Credentials come from deploy/.env (MQTT_USERNAME / MQTT_PASSWORD).
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
CERTS="$DIR/certs"
ENV_FILE="$DIR/../deploy/.env"
mkdir -p "$CERTS"

# --- build SAN list ---
SAN="DNS:mqtt,DNS:localhost,IP:127.0.0.1"
for host in "$@"; do
  if printf '%s' "$host" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    SAN="$SAN,IP:$host"
  else
    SAN="$SAN,DNS:$host"
  fi
done
echo "SANs: $SAN"

# --- CA (reuse if present so re-runs don't invalidate deployed agents) ---
if [ ! -f "$CERTS/ca.crt" ]; then
  echo "Generating CA…"
  openssl req -x509 -newkey rsa:4096 -nodes -days 3650 \
    -keyout "$CERTS/ca.key" -out "$CERTS/ca.crt" \
    -subj "/CN=Honeyswarm CA" >/dev/null 2>&1
fi

# --- server cert signed by the CA ---
echo "Generating server certificate…"
openssl req -newkey rsa:4096 -nodes \
  -keyout "$CERTS/server.key" -out "$CERTS/server.csr" \
  -subj "/CN=honeyswarm-mqtt" >/dev/null 2>&1
openssl x509 -req -in "$CERTS/server.csr" \
  -CA "$CERTS/ca.crt" -CAkey "$CERTS/ca.key" -CAcreateserial \
  -out "$CERTS/server.crt" -days 3650 \
  -extfile <(printf "subjectAltName=%s\nextendedKeyUsage=serverAuth\n" "$SAN") >/dev/null 2>&1
rm -f "$CERTS/server.csr"

# Readable by the mosquitto container user.
chmod 644 "$CERTS/ca.crt" "$CERTS/server.crt" "$CERTS/server.key"
chmod 600 "$CERTS/ca.key"

# --- password file ---
if [ -f "$ENV_FILE" ]; then
  MQTT_USERNAME="$(grep -E '^MQTT_USERNAME=' "$ENV_FILE" | cut -d= -f2-)"
  MQTT_PASSWORD="$(grep -E '^MQTT_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
fi
MQTT_USERNAME="${MQTT_USERNAME:-honeyswarm}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"
if [ -z "$MQTT_PASSWORD" ]; then
  echo "ERROR: MQTT_PASSWORD not set in $ENV_FILE" >&2
  exit 1
fi
echo "Generating password file for user '$MQTT_USERNAME'…"
# mosquitto_passwd runs as root in the container; set perms there so the
# mosquitto user (uid 1883) can read it and the host chmod doesn't fail.
docker run --rm -v "$DIR:/work" eclipse-mosquitto:2 sh -c \
  "mosquitto_passwd -c -b /work/passwd '$MQTT_USERNAME' '$MQTT_PASSWORD' && chown 1883:1883 /work/passwd && chmod 640 /work/passwd" >/dev/null 2>&1

echo "Done. Generated: certs/{ca.crt,ca.key,server.crt,server.key} and passwd"
echo "Bring the stack up:  (cd deploy && docker compose up -d)"
