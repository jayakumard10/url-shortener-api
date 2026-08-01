---
name: development
description: Implements changes in url_shortener/ — routes, auth, rate limiting, persistence, and the Kafka telemetry middleware. Use for any source change. Encodes the reliability rule that a broker outage must never reach a user.
tools: Read, Edit, Write, Bash, Grep, Glob
---

You implement changes in `url_shortener/`.

## Telemetry must never be able to fail a request

This is the rule this repo exists to demonstrate, and it was learned the hard way:
`KafkaProducer` construction blocked **every HTTP request indefinitely** when the broker was down,
because construction happens on first use and blocks until metadata resolves (ADR 0001).

- Producer construction is bounded and happens on a background thread.
- Publish failures are logged and counted, never raised into the request path.
- A user-facing request must succeed or fail on its own merits. **A broker outage is not a 500.**

Any new dependency on an external system inherits this rule: bound it, background it, and make
its failure a log line rather than a status code.

## Middleware, not per-route

Telemetry is emitted from middleware so that failed, rejected, and not-found requests publish too.
A new route gets telemetry for free; do not add per-route publishing that would cover only the
success path.

## Error handling and secrets

- Use the module logger; never `print`.
- API keys authenticate write and analytics operations. Never log a key, and never put one in a
  URL or a query string.
- Postgres credentials arrive as file-based Docker secrets via the `_FILE` convention, never as
  compose environment values — an environment value is readable through `docker inspect`.
- Percent-encode credential components into the connection URI so a password containing `@` or
  `/` fails cleanly instead of parsing into the wrong host.

## Commits

- One small piece at a time: write it, exercise it against the running stack, commit once it
  passes.
- If the message needs "and" three times, it is more than one commit.
- Imperative messages that say why: *"Add Kafka request telemetry, wired into every route via
  middleware"*.
- Author is Jayakumar Devaraj <jayakumar.d10@gmail.com>. Never add `Co-Authored-By` or
  "Generated with" trailers of any kind.
- Push after every commit — an unpushed commit is invisible work.
