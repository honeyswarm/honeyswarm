# Honeyswarm

Honeypot orchestration and monitoring platform. Deploy Dockerized honeypots
across a fleet of remote hosts ("Hives"), collect their events centrally, and
manage everything from a web dashboard.

> **v2 rewrite.** This is the API-first rewrite of Honeyswarm. The original
> Flask/Salt/HPFeeds version is preserved under the **`v1-legacy`** git tag.

## Architecture

```
Browser ── React SPA ──┐
                       │ HTTPS/JSON + WSS
                  Caddy (web/)  ──► FastAPI (api/) ──► MongoDB    (config, entities, jobs)
                                          │        └─► OpenSearch (event search + analytics)
                                          │ MQTT (commands ↓ / status + events ↑)
                                          ▼
                                   MQTT broker (mqtt/, Mosquitto)
                                          ▲
                                   Hive Agent (agent/)
                                     ├─ Docker SDK → runs honeypot containers from manifests/
                                     └─ tails honeypot JSON logs → publishes to MQTT
```

- **No SaltStack** — a lightweight per-hive **agent** runs containers via the
  Docker SDK and talks to the controller over MQTT (outbound only, NAT-friendly).
- **No HPFeeds** — honeypots emit native **JSON logs**; the agent tails and ships
  them. MQTT is the single control + telemetry backbone.
- **MongoDB** for config/entities, **OpenSearch** for event search/dashboards.

## Layout

| Path | What |
|------|------|
| `api/` | FastAPI control plane (auth, hives, honeypots, instances, events, jobs, admin; MQTT ingest + control plane) |
| `agent/` | Hive agent — enroll, run honeypots via Docker, tail logs, heartbeat |
| `web/` | React + TypeScript + Vite dashboard (served by Caddy, proxies the API) |
| `manifests/` | Honeypot definitions (replaces the old Salt states) |
| `mqtt/` | Mosquitto broker config + ACLs |
| `deploy/` | docker-compose stack, Caddyfile, `.env.template` |

## Quick start

```bash
cd deploy
cp .env.template .env        # then edit secrets (JWT_SECRET, ADMIN_PASSWORD, …)
docker compose up -d --build
```

Open <http://localhost> and log in with the bootstrap admin
(`ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`).

### Enroll a hive

In the UI: **Hives → create** to get a one-line install command, then run it on
the hive host (needs Docker + the Docker socket). The agent enrolls over the API
and connects to MQTT.

### Add a honeypot

**Honeypots → import** a manifest (e.g. `cowrie`), then **Instances → deploy** it
to a hive. Attack events stream into the dashboard live.

## Development

- API: `cd api && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload`
- Web: `cd web && npm install && npm run dev`
- Agent: `cd agent && pip install -r requirements.txt && HONEYSWARM_URL=… ENROLL_TOKEN=… python -m honeyswarm_agent`
