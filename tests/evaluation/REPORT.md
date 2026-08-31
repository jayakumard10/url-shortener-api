# Evaluation tier — verification report

What this service does at the seam with a real broker, and what that has actually
caught. The other three tiers stop at the edge of this process; everything here was
observed against a running Kafka, and every claim below names the command that
produced it.

## Why this tier is the primary QA artefact for telemetry

Both real defects this repository has had were invisible to a green unit suite:

- **The producer-construction hang** (`docs/adr/0001`). Constructing `KafkaProducer`
  blocked the request thread indefinitely when the broker was unreachable, so
  `docker compose up` with the eventbus stack down hung every single request. Found
  by running the real stack, not by a test.
- **An advertised-listener misconfiguration in `agentic-sdlc-eventbus`.** Publishing
  appeared to succeed and nothing arrived. `KAFKA_BOOTSTRAP_SERVERS` now points at
  port 9093 (the `DOCKER_INTERNAL` listener) rather than 9092, whose `PLAINTEXT_HOST`
  advertisement resolves to the container itself. See that repo's `docs/adr/0001`.

A publish that goes nowhere is indistinguishable from a publish that works, from
inside this process. That is the whole reason this tier exists.

## The original cross-repo verification

Ran this repository's `postgres` + `api` alongside `agentic-sdlc-eventbus`'s real
broker and confirmed the platform's first genuine cross-repo event end to end:
`POST /shorten` → `GET /{code}` → consumed the resulting event directly off the
eventbus broker. It was correctly formed per the shared `agentic-events` envelope
schema — `scenario_type: "brownfield"`, `metrics` carrying
`status_code`/`latency_ms`/`is_404`/`is_rate_limited`, and `payload` carrying the
request's method, path and code.

That exercise is what found both defects above.

## The automated seam test

`test_event_reaches_the_broker.py` turns the manual exercise into something CI can
hold onto. It publishes through `publish_request_telemetry` — the real entry point
the middleware calls, not `producer.send` directly, so envelope construction and the
partition key are under test — then consumes the event back off the topic and parses
it with the shared `EventEnvelope`.

Skipped when no broker is reachable, so a plain `pytest` still runs clean on a laptop
with nothing started. Set `URL_SHORTENER_REQUIRE_BROKER=1` to turn that skip into a
failure: where a workflow has started a broker, an unreachable one means the run
proved nothing while reporting green, which is worse than failing.

### Run, 2026-08-31

Against `agentic-sdlc-eventbus`'s broker on `localhost:9092` (the `PLAINTEXT_HOST`
listener — the host is where a developer runs pytest; containers use 9093).

```
URL_SHORTENER_REQUIRE_BROKER=1 pytest tests/evaluation -q
1 passed
```

Both directions of the gate were checked rather than assumed:

```
KAFKA_BOOTSTRAP_SERVERS=localhost:1 pytest tests/evaluation -q
1 skipped                                                    exit 0

KAFKA_BOOTSTRAP_SERVERS=localhost:1 URL_SHORTENER_REQUIRE_BROKER=1 pytest tests/evaluation -q
Failed: URL_SHORTENER_REQUIRE_BROKER=1 but no broker reachable at localhost:1: NoBrokersAvailable
```

### What writing it cost, and what that says

Two failures on the way in, both worth recording because both looked like a broker
fault and neither was.

1. **Publishing during producer warm-up asserts nothing.** `_get_producer` joins
   construction for one second and then returns whatever it has, so a service's
   first request or two legitimately skip telemetry — deliberate, and the reason a
   broker outage cannot add latency to a response. The test published into that
   window, sent nothing, and reported "no event arrived". The fixture now waits for
   a ready producer before publishing.

2. **`seek_to_end()` is lazy.** kafka-python flags the partitions for reset and
   resolves the offset on the next `poll()` — which happened *after* the publish, so
   the consumer reset to an end that already contained the event and then waited for
   it forever. The publish succeeded, the topic's end offset advanced, and the
   consumer saw nothing: precisely the shape of the listener misconfiguration above.

   A standalone probe passed the whole time. It passed *because* it printed
   `position()` for diagnostics, and reading the position is itself what forces the
   offset lookup. The fixture now calls `position()` deliberately, with a comment
   saying why.

The general lesson is the one this tier keeps teaching: at this seam, "it published"
and "a consumer received it" are different claims, and only the second one is worth
anything.
