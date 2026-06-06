# Honeyswarm — working notes & TODO

Handoff doc so a new session doesn't re-learn everything. Pair with `README.md`
(user-facing) and the architecture overview there.

## What this is

Honeypot orchestration: a central **controller** (FastAPI + React + MongoDB +
OpenSearch + Mosquitto) manages remote **Hives** (hosts running a small **agent**
that launches Dockerized honeypots and ships their JSON-log events back over
**MQTT/TLS**). One-command install: `cp .env.example .env && docker compose up -d`.

## Repo map

| Path | What |
|---|---|
| `compose.yaml` (root) | full stack, project name `honeyswarm` |
| `.env.example` | all config; copy to `.env` |
| `api/app/` | FastAPI: `routers/` (auth, hives, agents, honeypots, instances, events, jobs, admin), `services/` (ingest, control_plane, normalizers), `core/` (config, security, deps, mqtt, refs, manifests), `db/` (mongo, opensearch, seed), `agent_install/` (install.sh/.ps1 templates) |
| `agent/honeyswarm_agent/` | hive agent: main, runner (Docker SDK), tailer, settings |
| `web/src/` | React+TS+Vite SPA (pages/, components/, api/client.ts, auth/) |
| `manifests/<name>/` | honeypot defs (`manifest.yaml` + config templates) |
| `mqtt/` | `mosquitto.conf`, `init.sh` (cert/passwd bootstrap), `acl` |
| `.github/workflows/` | `ci-api/ci-web/ci-agent` (path-filtered) + `publish-agent` |

## Git / infra state

- Monorepo: `github.com/honeyswarm/honeyswarm`, default branch **`main`**. v1 Flask
  code preserved under tag **`v1-legacy`**. Old `honeyswarm_broker` + `honeyswarm_states`
  repos archived. Many `honeyswarm_*_honeypot` image repos exist (the honeypot images).
- Agent image published to **`ghcr.io/honeyswarm/honeyswarm-agent:latest`** (public) by
  `publish-agent.yml` on pushes touching `agent/`.
- **The user manages git themselves now — do NOT auto-commit/push.** Make edits;
  let them commit. (As of this note: tree clean, all pushed, HEAD `60fc47c`.)
- `gh` is authed as kevthehermit but the token **lacks `read:packages`** (can't
  introspect GHCR via API).

## Current live deployment (dev)

- Controller running locally via `docker compose` at **172.21.1.215** (`.env` has
  `PUBLIC_URL=http://172.21.1.215:8080`, `MQTT_PUBLIC_HOST=172.21.1.215`).
- Admin login: `admin@honeyswarm.local` / value of `ADMIN_PASSWORD` in `.env`
  (dev placeholder `CHANGE_ME_admin_pw`).
- One remote **Hive on a VM** enrolled over TLS. Was debugging Cowrie there.

## In progress / immediate

- [ ] **Verify Cowrie end-to-end on the VM.** Just switched the manifest to the
      official **`cowrie/cowrie:latest`** image (the old `honeyswarm/honeyswarm_cowrie_honeypot`
      is ~6yr/Python3.7 — too old: modern SSH clients fail KEX `couldn't match all
      kex parts`). Next: on the VM, UI → Instances → remove Cowrie → deploy again
      (agent pulls the new image). Confirm SSH login attempts log and events reach
      the dashboard. Manifest change is live via bind mount (no controller rebuild).
- [ ] Re-install the agent on the VM to pick up the hardened `runner.py` (port
      freeing + cleanup-on-failure), the **UDP port** fix (conpot), pyrdp **command
      var-substitution**, and the new **self-update** capability — the published
      image updates on push, but the VM must re-pull once (re-run the install
      one-liner). After this one manual re-install, future agent updates can use
      the new "Update agent" button (see below).

- [x] **Agent self-update.** `POST /hives/{id}/update-agent` (UI: "Update agent"
      button on the Hives page) publishes an `update_agent` MQTT command. The agent
      (`runner.self_update`) pulls the target image (default `settings.agent_image`)
      and launches a one-shot **updater** container (`honeyswarm_agent/updater.py`,
      from the new image, mounts docker.sock) that removes the old agent and
      recreates it in place with the same binds/env/restart-policy. State survives
      (the `/var/lib/honeyswarm` bind) and running honeypots are untouched (separate
      containers). Rolls back to the previous image if the new one won't start; if
      the new image is broken enough that the updater never runs, the old agent just
      keeps running. **Bootstrap caveat:** a hive's *current* agent must already
      contain this code, so the very first rollout to existing hives is still a
      manual re-install. **Suggestion:** bump `agent/honeyswarm_agent/__init__.py`
      `__version__` per release so the Hives "Agent" column visibly confirms an
      update landed.

## Backlog

- [ ] **Port remaining honeypots to manifests.** Done: `cowrie`, `jsontest`,
      `pyrdp` (gosecure/pyrdp, JSONL mitm.json), `conpot` (honeynet/conpot, native
      JSON logger via our conpot.cfg), `http` + `wordpress` (both Beelzebub
      `m4r10/beelzebub`, env-only config, NDJSON on stdout). **Still TODO:** `f5`,
      `elasticsearch`, `saltstack` (bespoke HPFeeds images, no maintained JSON
      upstream — need image work or replacements) and `portscans` (needs runner
      `network_mode: host`, see below). **Prefer official/maintained upstream
      images.** Normalizers in `api/app/services/normalizers.py` now cover: cowrie,
      pyrdp, conpot, http, wordpress, generic.
      - **Verified locally (docker run, 2026-06-06):** conpot (all ICS servers
        start; HTTP hit → JSON event `{data_type,src_ip,dst_port}`), http +
        wordpress (Beelzebub serves, nests the request under an `event` key,
        emits NDJSON; normalizer reads `event.SourceIp` and skips framework
        lines; POST creds land in `event.Body`), pyrdp (binds 3389, writes JSONL
        `mitm.json` with `clientIp`). Still verify on the **VM/dashboard**: full
        MQTT→ingest path, pyrdp with a real `RDPTARGET`, conpot UDP mappings.
- [ ] **Runner `network_mode` support** (needed for `portscans`, which binds a
      large host-port range via host networking). The agent `runner.py` has no
      `network_mode`/arbitrary-`binds` support today. `manifests/` port syntax now
      supports `host:container/udp` (added for conpot).
- [ ] **Per-hive MQTT auth** (currently a single shared credential for controller +
      all agents). Stub exists at `mqtt/acl` (username==hive_id). Options: per-hive
      passwords issued at enrollment, or mTLS client certs. Would isolate hives on
      the bus.
- [ ] Publish **api + web** images to GHCR (only agent is published) so the whole
      controller can deploy remotely, not just hives. Mirror `publish-agent.yml`.
- [ ] Dashboard **charts** (currently tables) and **asciinema playback** for Cowrie
      TTY sessions (the legacy app had this; ingest the cowrie `*.tty`/session data).
- [ ] Enrollment **token hardening**: token travels in URL query (`?token=`) so it
      lands in access logs / history. It's validated + effectively one-time; consider
      POST or expiring `agent_token_hash` after first successful `register`.
- [ ] **Production checklist** in README: rotate `JWT_SECRET`/`ADMIN_PASSWORD`/all
      `*_PASSWORD`; set `MQTT_PUBLIC_HOST`; `docker compose restart mqtt` after SAN
      changes; make the GHCR agent image pull works (it's public now).
- [ ] Dependabot keeps the repo current; Node20 GH-action deprecation warnings are
      non-blocking but could be bumped.

## Gotchas (hard-won — don't relearn)

- **Beanie 2.x uses `pymongo.AsyncMongoClient`, NOT motor** (`db/mongo.py`). A
  freshly-assigned `Link` holds the Document (`.id`), not `.ref` — use
  `app/core/refs.py:link_id` when serializing.
- **OpenSearch**: needs the index template in `db/opensearch.py` or fields map as
  `text` and aggregations/sort break. First boot is flaky (`java.io.tmpdir` / "main
  class Cannot") → handled by `restart: unless-stopped` + healthcheck + api
  `depends_on opensearch: service_healthy`.
- **Docker Desktop/WSL**: single-file bind mounts flake after edits → mount the
  **directory** (see `compose.yaml` mqtt service + `mqtt-init`).
- **`web/` needs `.dockerignore`** (node_modules/dist) or the host glibc rollup
  binary poisons the musl image build (CI passes, local `compose build` fails).
- **Agent runs in a container but launches honeypots via the host Docker daemon**,
  so its `-v` source paths resolve on the **host**. The install scripts bind-mount
  the host `/var/lib/honeyswarm` at the same path so rendered configs + log dirs
  line up for sibling honeypot containers. Don't switch this back to a named volume.
- **`mosquitto_passwd -c`** uses O_EXCL (refuses existing file) → `init.sh` `rm -f`s
  first.
- **After changing `MQTT_PUBLIC_HOST`/`MQTT_EXTRA_SANS`**: the cert is regenerated
  but the running broker keeps serving the old one → `docker compose restart mqtt`.
- **MQTT is TLS-only on 8883** (no cleartext). Agents get the CA at `/agent/register`
  and persist it; verify against it. Cert SAN must include the host agents connect
  to (`MQTT_PUBLIC_HOST`).
- **Install endpoints** (`/agent/install.sh|ps1`) validate the token (charset regex
  + DB existence) to prevent reflected shell injection — keep that if refactoring.

## Verify / common commands

```bash
# bring up / redeploy controller (from repo root)
docker compose up -d --build
docker compose logs -f mqtt-init        # cert/passwd bootstrap
curl -s localhost:8080/health

# admin token
TOK=$(curl -s -X POST localhost:8080/auth/login -H 'content-type: application/json' \
  -d '{"email":"admin@honeyswarm.local","password":"<ADMIN_PASSWORD>"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# run the agent locally from source (host networking so localhost works)
cd agent && HONEYSWARM_STATE_DIR=/tmp/hs HONEYSWARM_URL=http://localhost:8080 \
  ENROLL_TOKEN=<token> python -m honeyswarm_agent

# lint matches CI
ruff check api/app api/tools agent/honeyswarm_agent --select F,E9
```

Event pipeline: honeypot JSON log → agent tails (`tailer.py`, `file` or `stdout`
mode per manifest) → publishes `{normalizer, honeypot_instance_id, payload}` to
`hive/{id}/events` → controller `ingest.py` normalizes → Mongo + OpenSearch → `/events`.
