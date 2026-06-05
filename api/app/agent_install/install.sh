#!/usr/bin/env bash
# Honeyswarm hive installer. Installs Docker if needed, then runs the agent,
# which enrolls with the controller and connects to MQTT over TLS.
#
# This file is a template served by the controller with the values filled in;
# fetch it with the one-liner shown in the Honeyswarm UI (Hives -> create).
set -euo pipefail

HONEYSWARM_URL="__HONEYSWARM_URL__"
ENROLL_TOKEN="__ENROLL_TOKEN__"
AGENT_IMAGE="__AGENT_IMAGE__"
CONTAINER_NAME="honeyswarm-agent"

echo "[honeyswarm] Installing hive agent..."

if [ "$(id -u)" -ne 0 ]; then
  echo "[honeyswarm] Please run as root, e.g. pipe the installer to 'sudo bash'." >&2
  exit 1
fi

# Install Docker if it isn't already present.
if ! command -v docker >/dev/null 2>&1; then
  echo "[honeyswarm] Docker not found - installing via https://get.docker.com ..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker 2>/dev/null || true
fi

echo "[honeyswarm] Pulling agent image ${AGENT_IMAGE} ..."
docker pull "${AGENT_IMAGE}"

# Replace any previous agent on this host.
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

echo "[honeyswarm] Starting agent ..."
docker run -d --name "${CONTAINER_NAME}" --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v honeyswarm_agent_state:/var/lib/honeyswarm \
  -e HONEYSWARM_URL="${HONEYSWARM_URL}" \
  -e ENROLL_TOKEN="${ENROLL_TOKEN}" \
  "${AGENT_IMAGE}"

echo "[honeyswarm] Done. Follow logs with: docker logs -f ${CONTAINER_NAME}"
