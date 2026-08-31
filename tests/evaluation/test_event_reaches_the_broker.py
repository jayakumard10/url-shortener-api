"""The telemetry seam from the real calling position: a broker, not a fake producer.

Every other tier stops at the edge of this process. The contract tier asserts what
`publish_request_telemetry` hands to *a* producer; nothing below this file asserts
that a real KafkaProducer, configured the way this service configures it, actually
lands a parseable event on the topic a consumer subscribes to. That gap is where
this repo's two real defects lived: the producer-construction hang of ADR 0001, and
an advertised-listener misconfiguration that made every publish silently go nowhere
while the unit suite stayed green.

Skipped, not failed, when no broker is reachable: the unit and contract tiers have
to run on a laptop with nothing started, and so does a plain `pytest`. Set
``URL_SHORTENER_REQUIRE_BROKER=1`` to turn that skip into a failure - which is what
any workflow that starts a broker first should do, because there an unreachable
broker means the run proved nothing while reporting green.

Bootstrap defaults to ``localhost:9092``, agentic-sdlc-eventbus's PLAINTEXT_HOST
listener, because the host is where a developer runs pytest. Containers reach the
same broker on 9093 and set KAFKA_BOOTSTRAP_SERVERS accordingly - see this repo's
docker-compose.yml.
"""

from __future__ import annotations

import json
import os
import time
import uuid

import pytest
from agentic_events import EventEnvelope

from url_shortener import telemetry

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REQUIRE_BROKER = os.environ.get("URL_SHORTENER_REQUIRE_BROKER") == "1"
CONSUME_TIMEOUT_S = 30.0
PRODUCER_READY_TIMEOUT_S = 30.0


def _no_broker(reason: str) -> None:
    """Fail where a broker was promised, skip where it was merely optional."""
    if REQUIRE_BROKER:
        pytest.fail(f"URL_SHORTENER_REQUIRE_BROKER=1 but {reason}")
    pytest.skip(reason)


@pytest.fixture()
def consumer_at_end():
    """A consumer parked at the end of the topic, so it sees only what this test sends.

    Assigned explicitly and seeked to the end rather than subscribed with a group:
    this test must not replay whatever the topic already holds, and it must not
    leave a committed group offset behind on a shared broker.
    """
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError

    try:
        consumer = KafkaConsumer(
            bootstrap_servers=BOOTSTRAP,
            consumer_timeout_ms=1000,
            enable_auto_commit=False,
        )
    except KafkaError as exc:
        _no_broker(f"no broker reachable at {BOOTSTRAP}: {exc}")

    partitions = consumer.partitions_for_topic(telemetry.TOPIC)
    if not partitions:
        consumer.close()
        _no_broker(f"topic {telemetry.TOPIC} does not exist on {BOOTSTRAP}")

    from kafka import TopicPartition

    assignment = [TopicPartition(telemetry.TOPIC, p) for p in partitions]
    consumer.assign(assignment)
    consumer.seek_to_end(*assignment)

    # seek_to_end is lazy: it flags the partitions for reset and resolves the actual
    # offset on the next poll(). The first poll here happens *after* the test has
    # published, so without this the consumer resets to an end that already includes
    # the event under test and then waits forever for it. Reading position() forces
    # the lookup now, pinning the start before anything is sent.
    #
    # This cost a full debugging cycle and looked exactly like a broker fault: the
    # publish succeeded, the topic's end offset advanced, and the consumer saw
    # nothing. A standalone probe passed only because printing position() for
    # diagnostics was itself the thing that made it work.
    for partition in assignment:
        consumer.position(partition)

    yield consumer
    consumer.close()


@pytest.fixture()
def live_producer(monkeypatch):
    """Point telemetry at the real broker and wait for the producer to be ready.

    The producer, the failed flag and the construction thread are module globals
    that outlive a test. A previous test in the same session may have disabled
    telemetry permanently by setting _producer_init_failed, so this resets all
    three; monkeypatch restores them afterwards so nothing leaks into another tier.

    The warm-up loop is not ceremony. `_get_producer` joins construction for one
    second and then returns whatever it has, so a service's first request or two
    legitimately skip telemetry while the connection is still being established -
    deliberate, and the reason a broker outage cannot add latency to a response.
    Publishing into that window would make this test assert nothing while looking
    like a broker failure, which is precisely the false negative it exists to
    avoid. So it waits for a ready producer, then measures what a ready producer
    does. The warm-up path itself is covered in tests/unit/test_telemetry.py.
    """
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", BOOTSTRAP)
    monkeypatch.setattr(telemetry, "_producer", None)
    monkeypatch.setattr(telemetry, "_producer_init_failed", False)
    monkeypatch.setattr(telemetry, "_producer_init_thread", None)

    deadline = time.monotonic() + PRODUCER_READY_TIMEOUT_S
    producer = telemetry._get_producer()
    while producer is None and time.monotonic() < deadline:
        if telemetry._producer_init_failed:
            _no_broker(f"producer construction failed against {BOOTSTRAP}")
        producer = telemetry._get_producer()

    if producer is None:
        _no_broker(
            f"producer was not ready within {PRODUCER_READY_TIMEOUT_S}s against {BOOTSTRAP}"
        )
    yield producer


def test_a_published_event_arrives_on_the_topic_and_parses(consumer_at_end, live_producer):
    code = f"eval{uuid.uuid4().hex[:6]}"

    # The real entry point the middleware calls, not producer.send directly - the
    # envelope construction and the key choice are part of what is under test.
    telemetry.publish_request_telemetry(
        method="GET", path=f"/{code}", status_code=307, latency_ms=12.5, code=code
    )
    live_producer.flush(timeout=10)

    deadline = time.monotonic() + CONSUME_TIMEOUT_S
    received = None
    while received is None and time.monotonic() < deadline:
        for records in consumer_at_end.poll(timeout_ms=1000).values():
            for record in records:
                if record.key == code.encode("utf-8"):
                    received = record
                    break
            if received is not None:
                break

    assert received is not None, (
        f"no event with key {code} arrived on {telemetry.TOPIC} within {CONSUME_TIMEOUT_S}s. "
        "A green unit suite and a silent topic is exactly the advertised-listener failure "
        "this test exists to catch."
    )

    # Parsed with the shared contract, not with json alone: a consumer in another
    # repository does exactly this, and it is the step that fails if the envelope
    # drifts from the version this service pins.
    envelope = EventEnvelope.model_validate_json(received.value.decode("utf-8"))
    assert envelope.service == "url-shortener-api"
    assert envelope.event_type == "request-telemetry"
    assert envelope.scenario_type == "brownfield"
    assert envelope.metrics["status_code"] == 307
    assert envelope.payload["code"] == code

    # The partition key is what orders two events for one short link. It has to
    # survive serialization to the broker, not just the call to send().
    assert received.key == code.encode("utf-8")
    assert json.loads(received.value.decode("utf-8"))["schema_version"] == envelope.schema_version
