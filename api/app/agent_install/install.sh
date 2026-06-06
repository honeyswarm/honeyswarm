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

# Optional: --move-ssh [port]  relocates the host's SSH daemon off port 22 so an
# SSH honeypot (Cowrie) can bind it. Off by default (it changes how you reach
# this host). Default port 2222 if none given.
MOVE_SSH=""
while [ $# -gt 0 ]; do
  case "$1" in
    --move-ssh)
      if printf '%s' "${2:-}" | grep -qE '^[0-9]+$'; then MOVE_SSH="$2"; shift 2; else MOVE_SSH="2222"; shift; fi
      ;;
    --move-ssh=*) MOVE_SSH="${1#*=}"; shift ;;
    *) shift ;;
  esac
done

echo "[honeyswarm] Installing hive agent..."

if [ "$(id -u)" -ne 0 ]; then
  echo "[honeyswarm] Please run as root, e.g. pipe the installer to 'sudo bash'." >&2
  exit 1
fi

move_host_ssh() {
  port="$1"
  cfg="/etc/ssh/sshd_config"
  if [ "$port" = "22" ]; then
    echo "[honeyswarm] --move-ssh port must not be 22." >&2; exit 1
  fi
  echo "[honeyswarm] Moving host SSH to port ${port} to free port 22 for the honeypot..."
  cp "$cfg" "${cfg}.honeyswarm.bak" 2>/dev/null || true
  if grep -qiE '^[[:space:]]*#?[[:space:]]*Port[[:space:]]+' "$cfg"; then
    sed -i -E "s/^[[:space:]]*#?[[:space:]]*Port[[:space:]]+.*/Port ${port}/" "$cfg"
  else
    echo "Port ${port}" >> "$cfg"
  fi
  # Open the new port if ufw is active (best effort).
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "${port}/tcp" >/dev/null 2>&1 || true
  fi
  systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null \
    || service ssh restart 2>/dev/null || service sshd restart 2>/dev/null || true
  echo "[honeyswarm] ============================================================"
  echo "[honeyswarm]  Host SSH is now on port ${port}."
  echo "[honeyswarm]  Reconnect with:  ssh -p ${port} <user>@<host>"
  echo "[honeyswarm]  (existing sessions stay open; backup: ${cfg}.honeyswarm.bak)"
  echo "[honeyswarm] ============================================================"
}

[ -n "$MOVE_SSH" ] && move_host_ssh "$MOVE_SSH"

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

# Bind-mount a HOST path at the same path inside the agent. The agent launches
# honeypots via the host Docker daemon, so the dirs it creates (rendered config,
# log dirs) must exist at identical paths on the host for those bind-mounts to
# line up. A named volume would not be visible to sibling honeypot containers.
mkdir -p /var/lib/honeyswarm

echo "[honeyswarm] Starting agent ..."
docker run -d --name "${CONTAINER_NAME}" --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /var/lib/honeyswarm:/var/lib/honeyswarm \
  -e HONEYSWARM_URL="${HONEYSWARM_URL}" \
  -e ENROLL_TOKEN="${ENROLL_TOKEN}" \
  "${AGENT_IMAGE}"

echo "[honeyswarm] Done. Follow logs with: docker logs -f ${CONTAINER_NAME}"
