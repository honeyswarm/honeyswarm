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

Open <https://localhost> and log in with the bootstrap admin
(`ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`).

> **TLS / certificates.** The UI is served over **HTTPS** (Caddy terminates TLS at
> the edge; everything behind it runs on the private Docker network). By default
> Caddy issues a **self-signed** certificate on demand for whatever hostname or IP
> you browse to — zero config, but your browser shows a one-time trust warning
> (accept it, or import Caddy's local root CA). For a public domain with trusted
> Let's Encrypt certs, set `SITE_ADDRESS=<your-domain>` in `.env` and change the
> `tls internal { on_demand }` line in [`web/Caddyfile`](web/Caddyfile) to your
> email — Caddy then provisions and renews real certs automatically.

**OpenSearch Dashboards** (event search, charts, ad-hoc queries) is available at
**`/dashboards`**, via the **Dashboards ↗** link in the sidebar. It is *not*
published on its own port — it's proxied behind your existing Honeyswarm login
(**single sign-on**), so there is no separate Dashboards credential to manage.

For a **remote** deployment, set these in `.env` before first boot so hives can
reach and verify the controller:

- `MQTT_PUBLIC_HOST` — the controller's public hostname/IP; baked into the broker
  certificate's SAN so agents can verify the MQTT TLS connection.
- `PUBLIC_URL` — the base URL agents use to enroll, through the HTTPS edge
  (e.g. `https://honeyswarm.example.com`). Enrollment is proxied by Caddy; the
  API's `:8080` is **not** published to the host. It's what the generated install
  one-liner points at, so it must be reachable from the hives.
- `AGENT_TLS_VERIFY` — leave `false` for the default self-signed edge cert (the
  install one-liner is emitted with `curl -k`); set `true` once `PUBLIC_URL` uses
  a trusted (Let's Encrypt) cert so agents verify it.

> If you change `MQTT_PUBLIC_HOST` (or `MQTT_EXTRA_SANS`) after the first boot,
> the cert is regenerated but the running broker keeps serving the old one until
> restarted: `docker compose restart mqtt`.

### Enroll a hive

In the UI: **Hives → create** to get a per-hive install one-liner (copy it from
there — it has the right URL, token, and TLS flags filled in). Run it on the hive
host — it fetches an install script that installs Docker (if missing) and starts
the agent, which enrolls through the controller's HTTPS edge, receives the broker
CA, and connects to MQTT over TLS.

```bash
# Linux (run as root). -k skips cert verification for the default self-signed
# edge cert; drop it once the controller uses a trusted cert.
curl -fsSLk "https://<controller>/agent/install.sh?token=<token>" | sudo bash
```
```powershell
# Windows — Docker Desktop with Linux containers (PowerShell 7+).
irm -SkipCertificateCheck "https://<controller>/agent/install.ps1?token=<token>" | iex
```

A hive only needs outbound network access to the controller (HTTPS edge + MQTT);
the agent never accepts inbound connections.

**SSH honeypots** (e.g. Cowrie) bind host port 22, which the host's real `sshd`
already uses. Use the SSH-honeypot install one-liner (also shown in the UI) to
relocate the host SSH daemon first:

```bash
curl -fsSLk "https://<controller>/agent/install.sh?token=<token>" | sudo bash -s -- --move-ssh 2222
```

This moves host SSH to port 2222 (reconnect with `ssh -p 2222`; a backup of
`sshd_config` is kept) and frees port 22 for the honeypot.

### Add a honeypot

**Honeypots → import** a manifest (e.g. `cowrie`), then **Instances → deploy** it
to a hive. Attack events stream into the dashboard live.

## Configuration

All configuration is environment variables — see [`.env.example`](.env.example)
for the full list (MongoDB/OpenSearch/MQTT connections, JWT, the bootstrap admin,
the published agent image, and the public host/SANs for remote deployments).

Edge/TLS knobs worth calling out:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SITE_ADDRESS` | `:443` | Caddy's bind address. Leave as-is for zero-config self-signed HTTPS on any host/IP; set to `<your-domain>` for a named site (pair with a real-cert `tls` line in `web/Caddyfile`). |
| `COOKIE_SECURE` | `true` | `Secure` flag on the Dashboards SSO cookie. Keep `true` (HTTPS); only set `false` if you deliberately run the edge on plain HTTP. |

**Security model.** The reverse proxy (Caddy) is the trust boundary: it terminates
TLS and authenticates browsers, then talks to the API, OpenSearch, and Dashboards
over plain HTTP on the private `honeynet` Docker network. MongoDB and OpenSearch are
**not** published to the host; Dashboards is reachable only through the
SSO-gated `/dashboards` proxy. MQTT (for hives) is the one data-plane port exposed,
secured with TLS + authentication.

## Development

- API: `cd api && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload`
- Web: `cd web && npm install && npm run dev`
- Agent: `cd agent && pip install -r requirements.txt && HONEYSWARM_URL=… ENROLL_TOKEN=… python -m honeyswarm_agent`
