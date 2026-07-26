"""Unit tests for url_shortener.telemetry: envelope construction, the disabled-when-
unconfigured no-op path, and the publish call shape against a fake producer.
"""

from __future__ import annotations

import json

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


def test_build_envelope_sets_brownfield_scenario_and_metrics():
    envelope = telemetry.build_envelope(
        method="GET", path="/abc1234", status_code=307, latency_ms=12.5, code="abc1234"
    )
    assert envelope.service == telemetry.SERVICE_NAME
    assert envelope.event_type == "request-telemetry"
    assert envelope.scenario_type == "brownfield"
    assert envelope.metrics["status_code"] == 307
    assert envelope.metrics["is_404"] is False
    assert envelope.metrics["is_rate_limited"] is False
    assert envelope.payload["code"] == "abc1234"


def test_build_envelope_flags_404_and_429():
    not_found = telemetry.build_envelope(
        method="GET", path="/nope", status_code=404, latency_ms=1.0, code=None
    )
    assert not_found.metrics["is_404"] is True

    rate_limited = telemetry.build_envelope(
        method="POST", path="/shorten", status_code=429, latency_ms=1.0, code=None
    )
    assert rate_limited.metrics["is_rate_limited"] is True


def test_publish_is_noop_when_kafka_bootstrap_servers_unset(monkeypatch):
    monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
    monkeypatch.setattr(telemetry, "_producer", None)
    monkeypatch.setattr(telemetry, "_producer_init_failed", False)

    # Must not raise even though no broker is configured or reachable.
    telemetry.publish_request_telemetry(
        method="GET", path="/health", status_code=200, latency_ms=0.5, code=None
    )


def test_publish_sends_serialized_envelope_to_fake_producer(monkeypatch):
    fake_producer = _FakeKafkaProducer()
    monkeypatch.setattr(telemetry, "_get_producer", lambda: fake_producer)

    telemetry.publish_request_telemetry(
        method="GET", path="/abc1234", status_code=307, latency_ms=9.9, code="abc1234"
    )

    assert len(fake_producer.sent) == 1
    sent = fake_producer.sent[0]
    assert sent["topic"] == telemetry.TOPIC
    assert sent["key"] == "abc1234"
    body = json.loads(sent["value"])
    assert body["metrics"]["status_code"] == 307
    assert body["scenario_type"] == "brownfield"


def test_on_send_error_increments_failure_counter():
    before = telemetry.publish_failures
    telemetry._on_send_error(RuntimeError("broker unreachable"))
    assert telemetry.publish_failures == before + 1


def test_middleware_calls_publish_with_resolved_path_param(client, monkeypatch):
    """End-to-end: a real request through the app's middleware stack must call
    publish_request_telemetry with the {code} path param resolved and the real
    response status code - not just that build_envelope/producer work in isolation.
    """
    calls = []
    monkeypatch.setattr(
        "url_shortener.main.telemetry.publish_request_telemetry",
        lambda **kwargs: calls.append(kwargs),
    )

    shorten_response = client.post("/shorten", json={"long_url": "https://example.com/x"})
    code = shorten_response.json()["code"]
    calls.clear()

    redirect_response = client.get(f"/{code}", follow_redirects=False)
    assert redirect_response.status_code == 307

    assert len(calls) == 1
    assert calls[0]["status_code"] == 307
    assert calls[0]["code"] == code
    assert calls[0]["method"] == "GET"
