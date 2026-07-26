# url-shortener-api

FastAPI URL shortener: `POST /shorten`, `GET /{code}` (redirect), `GET /{code}/stats`,
`GET /health`. API-key auth on write/analytics endpoints, an in-process fixed-window rate
limiter on `/shorten`, and a Kafka telemetry publish on every request. Own `postgres:16-alpine`
— no other repo may connect to it (locked decision 2, database-per-service).

For the cross-repo view (end-to-end signal trace, event contract, all 4 repos' compose files)
see the living Master Plan document at `C:\srcCode\4-repo-migration-PLAN.md`.

Ported from the monolith's `/target_app` with an `app` → `url_shortener` rename; fresh `git init`,
no monolith history preserved. Full migration record — every deviation from a literal lift-and-shift
and why — lives in the plan doc's section 6, not duplicated here.

## Kafka telemetry

Every request — not just successful `/shorten` calls — publishes a `request-telemetry` event to
`url-shortener.request-telemetry.v1` (partition key = the `{code}` path param, or `null` when a
request has none, e.g. `/health`). This is deliberately broader than "publish after a DB commit":
the platform's drift metrics (status-code distribution, 404-on-redirect rate,
rate-limit-rejection rate) need coverage of failed and rejected requests too, which don't touch
the database at all. The middleware runs *after* `call_next`, so for DB-mutating routes the
publish still happens strictly after that route's own Postgres commit — Repo 4's transactional
boundary (plan doc section 1) is preserved.

Publishing is best-effort and never blocks or fails the response (plan doc's Reliability
section): if `KAFKA_BOOTSTRAP_SERVERS` is unset, or the producer can't be constructed, or a send
fails, telemetry is silently skipped/logged — the HTTP response is unaffected either way. Tests
never set `KAFKA_BOOTSTRAP_SERVERS`, so telemetry is a guaranteed no-op in the test suite; no
mocking is needed for that path, and `tests/test_telemetry.py` covers the envelope/publish logic
directly against a fake producer instead.

**Bug found and fixed while integration-testing against a real broker**: the first implementation
didn't actually satisfy "never blocks" — constructing the `KafkaProducer` blocked the request
thread indefinitely when the broker was unreachable. `docker compose up` with the eventbus stack
down hung every request. Fixed by constructing the producer in a background thread that the
request path joins with a 1-second bound (`_PRODUCER_INIT_JOIN_TIMEOUT_S`): worst case, the first
request(s) after startup pay ~1s of added latency while the connection attempt resolves in the
background; every request after that is instant either way, whether the producer ends up ready or
disabled. See `url_shortener/telemetry.py`.

## Docker Compose integration verification

Ran the full stack (this repo's `postgres`+`api`, plus `agentic-sdlc-eventbus`'s real broker) and
confirmed the platform's first genuine cross-repo event end-to-end, not just unit-level:
`POST /shorten` → `GET /{code}` → consumed the resulting event directly off Repo 3's broker,
correctly formed per the plan doc's envelope schema (`scenario_type: "brownfield"`, `metrics`
including `status_code`/`latency_ms`/`is_404`/`is_rate_limited`, `payload` with the request's
method/path/code). This exercise is also what found two real bugs, both fixed and covered above and
in the plan doc's conflict C6: the producer-construction hang here, and a Kafka advertised-listener
misconfiguration in `agentic-sdlc-eventbus` itself (`KAFKA_BOOTSTRAP_SERVERS` now points at port
9093, not 9092 — see this repo's `docker-compose.yml` comment and eventbus's README for why).

## Unit test coverage report

```
35 passed in 3.50s

Name                          Stmts   Miss  Cover   Missing
-----------------------------------------------------------
url_shortener\__init__.py         0      0   100%
url_shortener\auth.py            10      0   100%
url_shortener\db.py              39      5    87%   60, 64-68
url_shortener\main.py            63      0   100%
url_shortener\models.py          14      0   100%
url_shortener\rate_limit.py      18      0   100%
url_shortener\repository.py      24      0   100%
url_shortener\schemas.py         14      0   100%
url_shortener\telemetry.py       55     14    75%   46-67, 82-90
-----------------------------------------------------------
TOTAL                           237     19    92%
```

The two coverage gaps are both deliberate, not oversights:
- `db.py` lines 60/64-68 (`init_db`/`get_session` real bodies) — tests substitute both via
  `monkeypatch`/`dependency_overrides` so the real DB never gets touched by the unit suite. Same
  gap existed in the monolith's original test suite; SQLite-backed integration coverage of these
  two functions comes from every other test indirectly (they run through the overridden versions).
- `telemetry.py` lines 46-67/82-90 (`_construct_producer`'s real `KafkaProducer` construction, and
  the background-thread join path in `_get_producer`) — needs an actual reachable-or-unreachable
  broker to exercise meaningfully; this is exactly the code path the Docker Compose integration run
  above exercised and where the producer-construction-hang bug was actually found. Covered at the
  integration level, not unit tests — line count went up (was 44/8/82%) because the reliability fix
  added the threading logic itself.

## Local development

```bash
python -m venv .venv && source .venv/Scripts/activate   # or .venv/bin/activate on Linux/WSL
pip install -r requirements.txt
pytest --cov=url_shortener --cov-report=term-missing
```

`agentic-events` is a private-repo git dependency (`agentic-sdlc-eventbus`) — this works locally
as long as your machine's git is already authenticated to GitHub as `jayakumard10` (the same
credential that already pushes to these repos).

## Running with Docker Compose

One-time setup — copy the secret templates and fill in real values:

```bash
cp secrets/postgres_password.txt.example secrets/postgres_password.txt
cp secrets/github_pat.txt.example secrets/github_pat.txt
# edit secrets/github_pat.txt: a fine-grained, read-only PAT scoped to agentic-sdlc-eventbus
```

```bash
docker compose up -d --build
docker compose ps   # wait for both services healthy
curl http://localhost:8000/health
```

`KAFKA_BOOTSTRAP_SERVERS` defaults to `host.docker.internal:9092` — bring up
`agentic-sdlc-eventbus`'s compose stack first if you want telemetry to actually land somewhere;
the API works fine without it (telemetry just gets skipped, logged once).

## CI

`.github/workflows/ci.yml` needs a repository secret **`EVENTBUS_READ_PAT`** (Settings → Secrets
and variables → Actions) — a fine-grained, read-only PAT scoped to `agentic-sdlc-eventbus`, used
both to `pip install` the private `agentic-events` dependency and to build the Docker image in
CI. This is a manual one-time setup step; the workflow will fail on `pip install`/`docker build`
until it's set.
