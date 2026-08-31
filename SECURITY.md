# Security policy

## Reporting a vulnerability

Report privately through GitHub Security Advisories — **Security → Report a
vulnerability** on this repository. That opens a private thread visible only to the
maintainer.

**Please do not open a public issue for a security problem**, and please do not include a
working exploit against a deployment you do not own.

Useful things to include: what an attacker gains, the smallest request sequence that
demonstrates it, and which of the boundaries below it crosses.

## What this service is, in security terms

A URL shortener with a deliberately small trust model. Knowing the model matters, because
several things that look like vulnerabilities are documented design decisions, and one
thing that looks fine is not.

### Authentication is a single shared API key

`POST /shorten` and `GET /{code}/stats` require an `X-API-Key` header. This is not user
authentication and does not pretend to be — it guards two specific abuse vectors:
anonymous link creation, and enumerating codes to read another link's click analytics.

Comparison uses `hmac.compare_digest` rather than `!=`, because a plain string comparison
short-circuits on the first mismatched byte and leaks the correct prefix length through
response timing.

**`GET /{code}` — the redirect — is deliberately public.** It is the recipient-facing flow
the service exists for and must not require a key. A report that the redirect endpoint is
unauthenticated is a report about the design, not a vulnerability in it.

### The API key has an insecure default, and that is a real gap

`API_KEY` falls back to `dev-local-api-key` when the environment variable is unset
(`url_shortener/auth.py`). `docker-compose.yml` does not set it, so the documented compose
stack runs on a publicly known constant, and other repositories in this platform hardcode
that constant in their demo scripts.

This is fine for local development and **not fine for any deployment reachable by anyone
else**. Set `API_KEY` explicitly. Treat the default as "auth is off".

### Secrets

The Postgres password is delivered as a Docker secret at
`/run/secrets/postgres_password`, never as an environment variable in the image. Only
`.example` templates are tracked under `secrets/`; real files are ignored, and the
`secret-hygiene` job in `.github/workflows/security.yml` asserts the end state rather than
trusting the ignore rule — `.gitignore` does nothing about a file added with `git add -f`
or committed before the rule existed.

If you believe a real secret has been committed, report it privately as above. Rotate
first; a `git rm --cached` does not remove it from history.

### Telemetry leaves this service

Every request publishes an event to `url-shortener.request-telemetry.v1` carrying the
request method, path, short code, status code and latency. **The long URL is not
published.** If you are adding a field, treat it as data leaving this trust boundary and
consider what a broker consumer should not learn.

### Rate limiting is per-process and in-memory

The fixed-window limiter on `/shorten` lives in process memory. Behind more than one
replica each replica has its own window, so the effective limit multiplies by the replica
count. It is abuse dampening, not a security control, and should not be relied on as one.

## Automated scanning

`.github/workflows/security.yml` runs on every pull request and weekly on a schedule —
weekly matters, because a new advisory lands against unchanged code:

- **`pip-audit`** against `requirements.txt`. `agentic-events` is skipped and says so: it
  is a git dependency and not on PyPI, so there is no advisory database for it.
- **`secret-hygiene`**, described above.
- **CodeQL** for Python.

This workflow is intentionally **not** a required status check. It reports without
blocking, which is the right shape for a scanner whose inputs change without anyone
touching the code.

### Known open advisories

As of 2026-08-31, `pip-audit` reports two, both in pinned dependencies and neither yet
addressed:

| Package | Version | Advisory | Fixed in |
|---|---|---|---|
| `python-dotenv` | 1.0.1 | PYSEC-2026-2270 | 1.2.2 |
| `pytest` | 8.3.4 | PYSEC-2026-1845 | 9.0.3 |

`pytest` is a test-only dependency and does not ship in the runtime image.
`python-dotenv` is imported nowhere in the tree and appears to be removable outright
rather than upgraded.

## Supported versions

This repository has no releases and no tags. `main` is the only supported state.
