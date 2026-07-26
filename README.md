# url-shortener-api

FastAPI URL shortener: `POST /shorten`, `GET /{code}` (redirect), `GET /{code}/stats`,
`GET /health`. API-key auth on write/analytics endpoints, an in-process fixed-window rate
limiter on `/shorten`, and a Kafka telemetry publish on every request. Own `postgres:16-alpine`
— no other repo may connect to it (locked decision 2, database-per-service).

## Tech stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) 0.136.1, Uvicorn 0.34.0
- **Database**: PostgreSQL 16 (Alpine), SQLAlchemy 2.0.36, psycopg 3.2.3
- **Events**: kafka-python-ng 2.2.3, `agentic-events` (shared envelope contract)
- **Auth**: API-key header (`hmac.compare_digest`), in-process fixed-window rate limiting
- **Testing**: pytest 8.3.4, pytest-cov 7.1.0, FastAPI `TestClient` (httpx 0.28.1)
- **Infra**: Docker Compose, Docker BuildKit secrets, GitHub Actions CI

## Architecture

```mermaid
flowchart TD
    client(["Client request"]) --> mw["telemetry middleware<br/>wraps every request"]
    mw --> routes["FastAPI routes<br/>/health · /shorten · /{code} · /{code}/stats"]
    routes -->|"/shorten, /{code}/stats"| auth["auth.require_api_key"]
    routes -->|"/shorten only"| ratelimit["rate_limit.is_allowed"]
    routes --> repo["repository.SQLAlchemyURLRepository"]
    repo --> pg[("postgres:16-alpine<br/>own container, own network")]
    mw -. "request-telemetry event<br/>best-effort, ~1s bound" .-> broker(["agentic-sdlc-eventbus broker<br/>host.docker.internal:9093"])
```

Auth and rate-limiting only gate the routes that need them (`/{code}` redirect stays public by
design — see `auth.py`'s docstring). The telemetry middleware wraps every request regardless of
which path it took, which is why it's drawn wrapping the whole flow rather than sitting after one
specific route.

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

A bug in the first implementation (blocking indefinitely when the broker was unreachable) and the
bounded background-thread fix are documented in `docs/adr/0001`.

## Docker Compose integration verification

Ran the full stack (this repo's `postgres`+`api`, plus `agentic-sdlc-eventbus`'s real broker) and
confirmed the platform's first genuine cross-repo event end-to-end, not just unit-level:
`POST /shorten` → `GET /{code}` → consumed the resulting event directly off Repo 3's broker,
correctly formed per the plan doc's envelope schema (`scenario_type: "brownfield"`, `metrics`
including `status_code`/`latency_ms`/`is_404`/`is_rate_limited`, `payload` with the request's
method/path/code). This exercise is also what found two real bugs: the producer-construction hang
(`docs/adr/0001`, this repo) and a Kafka advertised-listener misconfiguration in
`agentic-sdlc-eventbus` itself (`KAFKA_BOOTSTRAP_SERVERS` now points at port 9093, not 9092 - see
that repo's `docs/adr/0001`).

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

`KAFKA_BOOTSTRAP_SERVERS` defaults to `host.docker.internal:9093` — bring up
`agentic-sdlc-eventbus`'s compose stack first if you want telemetry to actually land somewhere;
the API works fine without it (telemetry just gets skipped, logged once).

## CI

`.github/workflows/ci.yml` needs a repository secret **`EVENTBUS_READ_PAT`** (Settings → Secrets
and variables → Actions) — a fine-grained, read-only PAT scoped to `agentic-sdlc-eventbus`, used
both to `pip install` the private `agentic-events` dependency and to build the Docker image in
CI. This is a manual one-time setup step; the workflow will fail on `pip install`/`docker build`
until it's set.
