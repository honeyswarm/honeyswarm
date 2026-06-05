#!/bin/sh
# One-shot MQTT bootstrap, run by the `mqtt-init` compose service before the
# broker starts. Idempotently generates the self-signed CA, server certificate
# and password file into the shared `mqtt_secrets` volume (/secrets).
#
# Secure by default (TLS + auth) with zero pre-run scripts: `docker compose up`
# is all that's needed. Re-runs are cheap — it only regenerates when something
# is missing or the SAN list changed, and the CA is kept stable so already
# enrolled agents keep trusting the broker.
set -eu

SECRETS=/secrets
MOSQ_UID=1883
mkdir -p "$SECRETS"

# --- desired SANs ---
SAN="DNS:mqtt,DNS:localhost,IP:127.0.0.1"
add_san() {
  host="$1"
  [ -z "$host" ] && return 0
  if printf '%s' "$host" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    entry="IP:$host"
  else
    entry="DNS:$host"
  fi
  case ",$SAN," in *",$entry,"*) return 0 ;; esac  # skip duplicates
  SAN="$SAN,$entry"
}
add_san "${MQTT_PUBLIC_HOST:-}"
for extra in ${MQTT_EXTRA_SANS:-}; do add_san "$extra"; done

USER="${MQTT_USERNAME:-honeyswarm}"
PASS="${MQTT_PASSWORD:-}"
if [ -z "$PASS" ]; then
  echo "ERROR: MQTT_PASSWORD is not set" >&2
  exit 1
fi

# --- fast path: everything present and SAN unchanged ---
if [ -f "$SECRETS/ca.crt" ] && [ -f "$SECRETS/server.crt" ] && [ -f "$SECRETS/passwd" ] \
   && [ -f "$SECRETS/.san" ] && [ "$(cat "$SECRETS/.san")" = "$SAN" ]; then
  echo "mqtt-init: secrets already present (SAN unchanged); nothing to do."
  exit 0
fi

echo "mqtt-init: generating MQTT secrets (SAN: $SAN)"
command -v openssl >/dev/null 2>&1 || apk add --no-cache openssl >/dev/null 2>&1

# --- CA (generate once; keep stable) ---
if [ ! -f "$SECRETS/ca.crt" ]; then
  echo "mqtt-init: creating CA"
  openssl req -x509 -newkey rsa:4096 -nodes -days 3650 \
    -keyout "$SECRETS/ca.key" -out "$SECRETS/ca.crt" \
    -subj "/CN=Honeyswarm CA" >/dev/null 2>&1
fi

# --- server certificate signed by the CA (reflects current SANs) ---
echo "mqtt-init: creating server certificate"
openssl req -newkey rsa:4096 -nodes \
  -keyout "$SECRETS/server.key" -out "$SECRETS/server.csr" \
  -subj "/CN=honeyswarm-mqtt" >/dev/null 2>&1
openssl x509 -req -in "$SECRETS/server.csr" \
  -CA "$SECRETS/ca.crt" -CAkey "$SECRETS/ca.key" -CAcreateserial \
  -out "$SECRETS/server.crt" -days 3650 \
  -extfile <(printf "subjectAltName=%s\nextendedKeyUsage=serverAuth\n" "$SAN") >/dev/null 2>&1
rm -f "$SECRETS/server.csr"

# --- password file (recreate; mosquitto_passwd -c refuses an existing file) ---
echo "mqtt-init: writing password file for user '$USER'"
rm -f "$SECRETS/passwd"
mosquitto_passwd -c -b "$SECRETS/passwd" "$USER" "$PASS"

printf '%s' "$SAN" > "$SECRETS/.san"

# --- permissions: broker runs as uid 1883 ---
chown "$MOSQ_UID:$MOSQ_UID" "$SECRETS"/* "$SECRETS/.san" 2>/dev/null || true
chmod 644 "$SECRETS/ca.crt" "$SECRETS/server.crt" "$SECRETS/server.key"
chmod 600 "$SECRETS/ca.key"
chmod 640 "$SECRETS/passwd"

echo "mqtt-init: done."
