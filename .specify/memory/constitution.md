# Constitution — url-shortener-api

The non-negotiables for this repository. Every spec under `specs/` is checked against
this file before it is planned, and every plan is checked again before it is
implemented. A change that contradicts an article does not proceed as a change; it
proceeds as an amendment to this file, with the reasoning written down.

These are not aspirations. Each article is here because it was learned, and most of them
cost something to learn.

---

## Article I — This is a tenant service, not platform infrastructure

A FastAPI URL shortener that owns its own `postgres:16-alpine`. It is deliberately not
named `agentic-sdlc-*`, because it is not part of that platform brand: it is the tenant
the platform operates on.

Two consequences that are easy to get backwards:

- **The domain-agnostic rule does not apply here.** The `agentic-sdlc-*` repositories
  must not learn a tenant's vocabulary. This repository *is* the tenant and may describe
  short codes, redirects and click analytics freely.
- **Database-per-service.** No other repository connects to this Postgres, and this
  service connects to no other repository's. A shared table is a coupling that survives
  every later attempt to separate the two.

It knows nothing of any other repository's internals beyond the shared `agentic-events`
envelope.

## Article II — A broker outage must never reach a user

Telemetry is best-effort, always. If `KAFKA_BOOTSTRAP_SERVERS` is unset, or the producer
cannot be constructed, or a send fails, telemetry is skipped and logged. The HTTP
response is unaffected in every one of those cases.

This is the article that has already been violated once. The first implementation
blocked the request thread indefinitely constructing a `KafkaProducer` against an
unreachable broker, so `docker compose up` without the eventbus stack hung every single
request — see `docs/adr/0001`. The rule is therefore stronger than "handle the error":

- **Every path that touches the broker is bounded in time.** Construction runs on a
  background thread with a join timeout; sends carry their own timeouts.
- **A publish is never awaited by a response.** The middleware publishes after
  `call_next`, so a route's own transaction has already committed.
- **Silence is reported.** A dropped event is invisible from outside the process, which
  is why `/health` exposes `configured`, `publishing` and `publish_failures` separately:
  configured-but-not-publishing is the state worth alerting on, and no single flag
  distinguishes it from telemetry being off on purpose.

## Article III — A green suite is not evidence about the seam

This repository's tests passing proves nothing about whether an event reached a
consumer. A publish that goes nowhere is indistinguishable from one that works, seen
from inside this process — that is exactly how an advertised-listener misconfiguration
in `agentic-sdlc-eventbus` once made every publish silently vanish while the suite
stayed green.

So a change to the telemetry seam is verified **from the real calling position**: an
event published through `publish_request_telemetry` and consumed back off the topic.
`tests/evaluation/` holds those tests and `tests/evaluation/REPORT.md` holds what they
found. Where a workflow starts a broker, an unreachable one is a failure and not a skip:
there, skipping means the run proved nothing while reporting green.

Never describe a workflow file as evidence. A run is evidence.

## Article IV — The layout is enforced by a test, or it is a suggestion

`tests/contract/test_repository_structure.py` asserts shape, never content: where the
package lives, that every test is in a tier directory, that ADRs are numbered without
gaps, that required files exist.

Without it, the next contributor inherits a tree that is *mostly* the documented one
with no way to tell which parts were deliberate.

Related and equally hard-won: **a test's tier marker comes from its directory, never
from the file.** A test with no marker is collected, counted in "passed", and skipped
entirely by a marker-filtered run. `--strict-markers` does not catch that — it catches a
*misspelled* marker, never a missing one. `tests/conftest.py` derives the marker from
the parent directory and raises a collection error for anything outside the tiers.

## Article V — Every claim needs a command that was run

A doc claim with nothing behind it is a bug, not a TODO. Not "the event reaches the
broker" — the consumed record. Not "the tests pass" — the exit code.

**Check exit codes, never summary lines.** `pytest` can print "38 passed" and exit 1,
and `cmd | tail -1` returns `tail`'s status rather than `cmd`'s.

**Isolate before blaming a dependency.** Run the failing thing against the previous
versions before attributing a failure to a bump. The corollary learned here: a
diagnostic can be the thing that makes a test pass — a probe of the evaluation tier
worked only because printing a consumer's `position()` is itself what forces the offset
lookup that the test needed.

## Article VI — This is an application, and it stays one

The package lives at the repository root. Nothing installs it: the container does
`pip install -r requirements.txt`, then `COPY . .`, then runs
`uvicorn url_shortener.main:app` with `WORKDIR /app`, so the package resolves because
the working directory is on `sys.path`.

- **No `src/` layout.** `src/` exists to stop tests importing the working tree instead
  of the installed wheel. There is no wheel, so it protects against nothing and breaks
  the container build. See `docs/adr/0002`.
- **No `[project]` table and no build backend.** `pyproject.toml` carries `[tool.*]`
  sections only.
- **`requirements.txt` stays the install mechanism**, with `requirements.lock` supplying
  the reproducibility that pinning alone does not: a transitive dependency can move
  under an unchanged pin, and a git tag can be moved outright.

## Article VII — Renaming a CI job breaks branch protection

Required status checks match a job's **display name**, not its key. A rename leaves the
ruleset waiting on a context nothing reports: every check green, the PR stuck at
`BLOCKED`.

The required contexts on `main` are `test` and `compose-smoke-test`. Renaming either one
means updating the ruleset in the same change. **Never require a path-filtered
workflow's check** — it does not report on a PR outside its paths, so requiring it
blocks those PRs forever.

## Article VIII — Small commits, and documentation that moves with the code

Build one piece, test it against something real, commit it. A commit message that needs
"and" three times is more than one commit.

When a decision is revised, a fix changes behaviour, or a pin moves, the documentation
changes in the **same** commit. Stale docs are a bug, not a TODO. Significant decisions
get an ADR under `docs/adr/NNNN-title.md` (Context / Decision / Consequences).

Commits are authored by Jayakumar Devaraj. No `Co-Authored-By` and no "Generated with"
trailers, in commits or PR bodies.
