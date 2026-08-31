"""What this service puts on the wire, asserted from a consumer's point of view.

This is the one thing url-shortener-api can break for another repository. It
publishes `url-shortener.request-telemetry.v1`, the platform's drift metrics read
those events, and until this file existed nothing anywhere checked that what
`build_envelope` produces is what a consumer can parse. The unit tier covers the
same function, but it asserts the two or three fields whichever test needed - it
would not notice a renamed metrics key or a field silently dropped from the wire
form.

**Validated against the installed `EventEnvelope`, not against a registry.**
`requirements.txt` pins `agentic-events` at `v0.1.0`, and that tag ships
`envelope.py` alone - no `registry` module and no per-topic JSON Schema. Schema
validation through `agentic_events.registry` needs a newer pin, which is a
dependency change rather than a structural one. What is available at this pin is
still a real contract: `EventEnvelope` is declared `extra="forbid"`, so a
round-trip through it rejects any field this service invents, and the assertions
below pin the field values and the partition key that consumers actually read.

No I/O: the producer is a fake and no broker is contacted.
"""

from __future__ import annotations

import json

from agentic_events import SCHEMA_VERSION, EventEnvelope

from url_shortener import telemetry


class _FakeFuture:
    def add_errback(self, callback):
        return self


class _FakeKafkaProducer:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, topic, key=None, value=None):
        self.sent.append({"topic": topic, "key": key, "value": value})
        return _FakeFuture()


def _publish(monkeypatch, **overrides) -> dict:
    """Publish one event through the real code path and return the wire form."""
    fake_producer = _FakeKafkaProducer()
    monkeypatch.setattr(telemetry, "_get_producer", lambda: fake_producer)

    kwargs = {
        "method": "GET",
        "path": "/abc1234",
        "status_code": 307,
        "latency_ms": 9.9,
        "code": "abc1234",
    }
    kwargs.update(overrides)
    telemetry.publish_request_telemetry(**kwargs)

    assert len(fake_producer.sent) == 1
    return fake_producer.sent[0]


def test_the_wire_form_round_trips_through_the_shared_envelope(monkeypatch):
    # extra="forbid" is what gives this teeth: a field added to build_envelope
    # that the shared contract does not declare fails here rather than reaching a
    # consumer that cannot parse it.
    sent = _publish(monkeypatch)
    parsed = EventEnvelope.model_validate_json(sent["value"])
    assert parsed.service == "url-shortener-api"
    assert parsed.event_type == "request-telemetry"
    assert parsed.scenario_type == "brownfield"


def test_the_schema_version_travels_on_the_wire(monkeypatch):
    # A consumer routes on this before it can trust any other field. Pydantic
    # would happily default it in on the way back out, so assert the serialized
    # form rather than the parsed object.
    body = json.loads(_publish(monkeypatch)["value"])
    assert body["schema_version"] == SCHEMA_VERSION


def test_the_topic_names_the_event_type_and_the_schema_major(monkeypatch):
    # The topic is the subscription a consumer writes down. It has to stay in
    # step with event_type and with the schema version, or a v2 envelope lands on
    # the v1 topic and every subscriber breaks at once.
    body = json.loads(_publish(monkeypatch)["value"])
    assert telemetry.TOPIC == f"url-shortener.{body['event_type']}.v1"
    assert SCHEMA_VERSION.startswith("1.")


def test_metrics_carries_exactly_the_four_keys_the_drift_reader_expects(monkeypatch):
    # Named exactly, not "contains": dropping a key breaks the reader loudly,
    # while quietly adding one grows the contract without anyone deciding to.
    body = json.loads(_publish(monkeypatch)["value"])
    assert set(body["metrics"]) == {"status_code", "latency_ms", "is_404", "is_rate_limited"}
    assert isinstance(body["metrics"]["status_code"], int)
    assert isinstance(body["metrics"]["latency_ms"], float)
    assert isinstance(body["metrics"]["is_404"], bool)
    assert isinstance(body["metrics"]["is_rate_limited"], bool)


def test_payload_carries_exactly_the_three_keys_the_contract_promises(monkeypatch):
    body = json.loads(_publish(monkeypatch)["value"])
    assert set(body["payload"]) == {"method", "path", "code"}


def test_the_boolean_metrics_derive_from_the_status_code(monkeypatch):
    # These exist so a consumer never has to know which status codes this service
    # considers a miss or a rejection. If they stopped tracking status_code the
    # drift metrics would go wrong silently rather than fail.
    not_found = json.loads(_publish(monkeypatch, status_code=404)["value"])["metrics"]
    assert not_found["is_404"] is True
    assert not_found["is_rate_limited"] is False

    limited = json.loads(_publish(monkeypatch, status_code=429)["value"])["metrics"]
    assert limited["is_404"] is False
    assert limited["is_rate_limited"] is True


def test_the_partition_key_is_the_short_code(monkeypatch):
    # Kafka orders per partition, not per topic. Keying on the code is what makes
    # two events for one short link arrive in the order they happened, so this is
    # consumer-visible behaviour and not an implementation detail.
    assert _publish(monkeypatch, code="abc1234")["key"] == "abc1234"


def test_a_request_with_no_short_code_publishes_a_null_key(monkeypatch):
    # /health has no {code}. A null key means Kafka distributes these rather than
    # heaping every keyless event onto one partition.
    sent = _publish(monkeypatch, method="GET", path="/health", status_code=200, code=None)
    assert sent["key"] is None
    assert json.loads(sent["value"])["payload"]["code"] is None
