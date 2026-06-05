#!/usr/bin/env sh
# Generate / append a Mosquitto password entry for production hardening.
# Usage: ./mqtt/gen-passwd.sh <username> <password>
# Creates mqtt/passwd (chmod 0700) which you then mount + enable in mosquitto.conf.
set -eu

USER="${1:?usage: gen-passwd.sh <username> <password>}"
PASS="${2:?usage: gen-passwd.sh <username> <password>}"
DIR="$(cd "$(dirname "$0")" && pwd)"
PWFILE="$DIR/passwd"

touch "$PWFILE"
docker run --rm -v "$PWFILE:/passwd" eclipse-mosquitto:2 \
    mosquitto_passwd -b /passwd "$USER" "$PASS"
chmod 0700 "$PWFILE"
echo "Wrote $USER to $PWFILE"
