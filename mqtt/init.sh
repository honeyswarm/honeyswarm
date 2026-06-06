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

# Controller identity. The broker uses the client cert CN as the MQTT username
# (use_identity_as_username), so this must match the controller user in the ACL.
USER="${MQTT_USERNAME:-honeyswarm}"

# --- fast path: everything present and SAN unchanged ---
if [ -f "$SECRETS/ca.crt" ] && [ -f "$SECRETS/server.crt" ] \
   && [ -f "$SECRETS/client-$USER.crt" ] && [ -f "$SECRETS/client-$USER.key" ] \
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

# ext files (a temp file, not process substitution, so this stays POSIX-portable
# across dash / busybox-ash / bash).
EXT="$SECRETS/.ext"

# --- server certificate signed by the CA (reflects current SANs) ---
echo "mqtt-init: creating server certificate"
openssl req -newkey rsa:4096 -nodes \
  -keyout "$SECRETS/server.key" -out "$SECRETS/server.csr" \
  -subj "/CN=honeyswarm-mqtt" >/dev/null 2>&1
printf "subjectAltName=%s\nextendedKeyUsage=serverAuth\n" "$SAN" > "$EXT"
openssl x509 -req -in "$SECRETS/server.csr" \
  -CA "$SECRETS/ca.crt" -CAkey "$SECRETS/ca.key" -CAcreateserial \
  -out "$SECRETS/server.crt" -days 3650 \
  -extfile "$EXT" >/dev/null 2>&1
rm -f "$SECRETS/server.csr"

# --- controller client certificate (mutual TLS; CN == ACL controller user) ---
echo "mqtt-init: creating controller client certificate (CN=$USER)"
openssl req -newkey rsa:4096 -nodes \
  -keyout "$SECRETS/client-$USER.key" -out "$SECRETS/client-$USER.csr" \
  -subj "/CN=$USER" >/dev/null 2>&1
printf "extendedKeyUsage=clientAuth\n" > "$EXT"
openssl x509 -req -in "$SECRETS/client-$USER.csr" \
  -CA "$SECRETS/ca.crt" -CAkey "$SECRETS/ca.key" -CAcreateserial \
  -out "$SECRETS/client-$USER.crt" -days 3650 \
  -extfile "$EXT" >/dev/null 2>&1
rm -f "$SECRETS/client-$USER.csr" "$EXT"

printf '%s' "$SAN" > "$SECRETS/.san"

# --- permissions: broker runs as uid 1883; the API (root) reads the CA key ---
chown "$MOSQ_UID:$MOSQ_UID" "$SECRETS"/* "$SECRETS/.san" 2>/dev/null || true
chmod 644 "$SECRETS/ca.crt" "$SECRETS/server.crt" "$SECRETS/client-$USER.crt"
chmod 600 "$SECRETS/ca.key" "$SECRETS/server.key" "$SECRETS/client-$USER.key"

echo "mqtt-init: done."
