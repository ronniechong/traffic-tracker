# CLAUDE.md — traffic-tracker

Tracks freeway travel-time and congestion conditions across metropolitan Melbourne, Victoria, using the VIC open data portal's Freeway Travel Time API (`/traffic` + `/gis` endpoints).

## Data source
- Auth: subscription key sent via a **`KeyId`** header — not `Ocp-Apim-Subscription-Key` as the published OpenAPI spec states (that header returns 401). Key lives in `.env` only, never committed, never logged.
- Coverage: 12 freeways, 246 segments (Monash Fwy, EastLink, West Gate Fwy, Tullamarine Fwy, Western Ring Rd, Eastern Fwy, Mornington Peninsula Fwy, Calder Fwy, Metropolitan Ring Rd, South Gippsland Fwy, Princes Fwy, West Gate Tunnel). CityLink and Hume Fwy are not covered by this dataset.
- Primary condition field: `condition` (categorical: Light/Medium/Heavy/Blank). `congestionIndex` exists but is present on <1% of segments — not usable as a primary field.
- `dataSubstitution` is a 0-100 interpolation/confidence indicator, nonzero on roughly a third of readings — gap/fallback rendering for high-substitution segments is core v1 scope, not a stretch goal.
- `/traffic` is the more complete geometry source of the two endpoints (fewer null-geometry segments than `/gis`) — `/gis` is not a reliable fallback for `/traffic`'s geometry gaps.
- `type` (from `/gis`) is a constant classification tag across all segments, not a useful filter dimension.
- Update cadence: uniform ~120 seconds per segment (not the ~30s the API's documentation states). All records publish in Victorian local time (not UTC) — this is a deliberate difference from typical UTC-everywhere convention and must be handled explicitly in storage/display.
- No observable rate-limit enforcement was found during testing, but the client self-limits to a conservative cadence regardless — treat the limit as real even though it wasn't directly observed.

## Architecture decisions
| Decision | Choice | Why |
|---|---|---|
| Language/tooling | Python 3.12, `uv` | Consistent, reproducible builds |
| Containerization | Docker Compose, self-hosted | Full control over egress, non-root/read-only containers |
| Storage | Day-partitioned SQLite (UTC day boundary), 90-day rolling local retention by unconditional file deletion | Simple single-writer relational storage; day boundaries also suit periodic archival export; retention deletion never depends on export status, so a stalled archiver can't silently block cleanup |
| Eventing | Plain polling for v1; Service Worker + stale-while-revalidate planned as a frontend enhancement, with Periodic Background Sync as a progressive enhancement where supported | ~120s cadence doesn't justify a persistent connection (SSE) |
| Frontend | Static site on GitHub Pages, MapLibre GL, served from a custom domain apex rather than the default `github.io` path | Free hosting, no server-rendering needed |
| Backend exposure | Tailscale Funnel | No public inbound ports on the host beyond controlled ingress |
| Monitoring | Prometheus metrics endpoint + external dead-man's-switch pings | Detects both internal stalls and external reachability failures |
| Map rendering | MapLibre GL + OpenFreeMap (`liberty`/`dark` styles), condition-colored line layer over live segment geometry, no CityLink connector rendered | Free/keyless tile source; CityLink has no public data source at all, so there is no segment to render through the CBD rather than a styled placeholder standing in for missing data |

## Security invariants
1. Exactly one upstream consumer. No code path may trigger a request to the upstream API from a user action — a single poller process is the only client.
2. API key via environment only. Never in this repo, logs, client code, or docs. Redaction filter active from day one.
3. Public surface is GET-only derived state: strict CORS from an env origin list, connection caps, rate limiting at the ingress.
4. The API binds to localhost; the reverse proxy is the only ingress.
5. Containers: non-root, read-only root filesystem, a single writable data mount, egress-restricted poller, `restart: unless-stopped`.
6. This repo is public: gitleaks runs pre-commit and in CI; `.env`, `data/`, `*.db` are gitignored.
7. Any future AI/aggregation layer: upstream feed text is untrusted data, never instructions; hard budget caps and per-run token limits; every inference labelled with its evidence.

## Comment scope
Code comments explain non-obvious **why** — a hidden constraint, a subtle invariant, a workaround for a specific bug — not a running decision log. Default to no comment. No timestamps, no "changed from X to Y because...", no restating what the diff already shows.

No references to internal docs, planning artifacts, or process/discussion history: no milestone numbers or labels, no "spec-review", no paths to any private working-docs repo, no "resolved during X session/discussion". State the technical rationale itself (what's true about the system or the data) instead of citing where or when it was decided. This applies to docstrings and inline comments alike, everywhere in this repo, not just files that look sensitive at a glance.
