# Honeyswarm

Honeypot orchestration and monitoring platform. Deploy Dockerized honeypots
across a fleet of remote hosts ("Hives"), collect their events centrally, and
manage everything from a web dashboard.

## Architecture

```
Browser ── React SPA ──┐
                       │ HTTPS/JSON + WSS
                  Caddy (web/)  ──► FastAPI (api/) ──► MongoDB    (config, entities, jobs)
                                          │        └─► OpenSearch (event search + analytics)
                                          │ MQTT/TLS (commands ↓ / status + events ↑)
                                          ▼
                                   MQTT broker (mqtt/, Mosquitto)
                                          ▲
                                   Hive Agent (agent/)
                                     ├─ Docker SDK → runs honeypot containers from manifests/
                                     └─ tails honeypot JSON logs → publishes to MQTT
```

- A lightweight per-hive **agent** runs honeypot containers via the Docker SDK and
  talks to the controller over MQTT — outbound only, so hives stay NAT/firewall friendly.
- Honeypots emit native **JSON logs**; the agent tails and ships them. MQTT is the
  single control + telemetry backbone, secured with TLS and authentication.
- **MongoDB** stores config and entities; **OpenSearch** powers event search and dashboards.

## Layout

| Path | What |
|------|------|
| `api/` | FastAPI control plane: auth, hives, honeypots, instances, events, jobs, admin, plus the MQTT ingest + control plane |
| `agent/` | Hive agent — enroll, run honeypots via Docker, tail logs, heartbeat |
| `web/` | React + TypeScript + Vite dashboard (served by Caddy, which proxies the API) |
| `manifests/` | Honeypot definitions (image, ports, config template, log normalizer) |
| `mqtt/` | Mosquitto broker config, ACLs, and the `init.sh` cert/passwd bootstrap |
| `compose.yaml` | the full Docker Compose stack |

## Quick start

```bash
cp .env.example .env         # then edit secrets (JWT_SECRET, ADMIN_PASSWORD, *_PASSWORD)
docker compose up -d --build
```

That's it — the `mqtt-init` service generates the broker's TLS certificate and
password file on first boot (into a Docker volume), so there are no pre-run scripts.

Open <http://localhost> and log in with the bootstrap admin
(`ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`).

For a **remote** deployment, set `MQTT_PUBLIC_HOST` in `.env` to the controller's
public hostname/IP before first boot — it's baked into the broker certificate's
SAN so agents on remote hives can verify it.

### Enroll a hive

In the UI: **Hives → create** to get a per-hive install one-liner. Run it on the
hive host — it fetches an install script that installs Docker (if missing) and
starts the agent, which enrolls over the API, receives the broker CA, and
connects to MQTT over TLS.

```bash
# Linux (run as root)
curl -fsSL "https://<controller>/agent/install.sh?token=<token>" | sudo bash
```
```powershell
# Windows — Docker Desktop with Linux containers
irm "https://<controller>/agent/install.ps1?token=<token>" | iex
```

A hive only needs outbound network access to the controller (API + MQTT); the
agent never accepts inbound connections.

### Add a honeypot

**Honeypots → import** a manifest (e.g. `cowrie`), then **Instances → deploy** it
to a hive. Attack events stream into the dashboard live.

## Configuration

All configuration is environment variables — see [`.env.example`](.env.example)
for the full list (MongoDB/OpenSearch/MQTT connections, JWT, the bootstrap admin,
the published agent image, and the public host/SANs for remote deployments).

## Development

- API: `cd api && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload`
- Web: `cd web && npm install && npm run dev`
- Agent: `cd agent && pip install -r requirements.txt && HONEYSWARM_URL=… ENROLL_TOKEN=… python -m honeyswarm_agent`
