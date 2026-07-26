# 0001: Bound `KafkaProducer` construction with a background thread

Date: 2026-07-26
Status: Accepted

## Context

The reliability design for `telemetry.py` requires that an unreachable Kafka broker never affects
the HTTP response — best-effort publish, log and count failures, always return normally. The first
implementation didn't actually satisfy this: constructing `KafkaProducer` blocked the request
thread indefinitely when the broker was unreachable. Bringing up `docker compose up` with the
`agentic-sdlc-eventbus` stack down hung every single request, discovered only by running the real
stack, not by unit tests (which never set `KAFKA_BOOTSTRAP_SERVERS`, so this code path was never
exercised in the test suite at all).

## Decision

Construct the `KafkaProducer` in a background thread that the request path joins with a 1-second
bound (`_PRODUCER_INIT_JOIN_TIMEOUT_S`). Worst case, the first request(s) after startup pay ~1s of
added latency while the connection attempt resolves in the background; every request after that is
instant either way, whether the producer ends up ready or disabled.

## Consequences

- `telemetry.py`'s `_get_producer()` no longer blocks the caller regardless of broker
  reachability - the reliability requirement is now actually met, not just claimed.
- This exact pattern (bounded background-thread producer construction) was reused as-is in
  `agentic-sdlc-mlops`'s `events.py` for the same reason, rather than re-deriving it per repo.
- General lesson: a reliability claim ("never blocks") needs to be tested against the actual
  failure condition it claims to handle (broker down), not just against the happy path.
