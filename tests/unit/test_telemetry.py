"""Unit tests for url_shortener.telemetry: envelope construction, the disabled-when-
unconfigured no-op path, the publish call shape against a fake producer, and the
bounded-construction guarantee that keeps an unreachable broker out of the request path.
"""

from __future__ import annotations

import json
import threading
import time

import kafka

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


def test_an_unreachable_broker_never_holds_up_the_request_path(monkeypatch):
    """ADR 0001's guarantee, driven through the real mechanism.

    `KafkaProducer` construction against a broker that accepts the connection and
    then never answers used to block every HTTP request for as long as it took to
    give up. The fix moves construction to a background thread that the request path
    only ever joins *with a timeout*.

    This test deliberately does not patch `_get_producer` away, unlike the tests
    around it: the thread, the lock and the join timeout are the things under test.
    Remove any of them and the call below inherits the constructor's full stall
    instead of the join timeout, and this fails.
    """
    release = threading.Event()
    constructing = threading.Event()

    class _NeverAnswers:
        def __init__(self, **kwargs):
            constructing.set()
            # Stands in for a broker that holds the connection open and says nothing.
            release.wait(timeout=30)
            raise AssertionError("broker never answered")

    monkeypatch.setattr(kafka, "KafkaProducer", _NeverAnswers)
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker.invalid:9092")
    monkeypatch.setattr(telemetry, "_producer", None)
    monkeypatch.setattr(telemetry, "_producer_init_failed", False)
    monkeypatch.setattr(telemetry, "_producer_init_thread", None)
    monkeypatch.setattr(telemetry, "_PRODUCER_INIT_JOIN_TIMEOUT_S", 0.2)

    started = time.perf_counter()
    telemetry.publish_request_telemetry(
        method="GET", path="/health", status_code=200, latency_ms=0.5, code=None
    )
    elapsed = time.perf_counter() - started

    # Let the background construction unwind before monkeypatch restores the globals
    # it is about to write to.
    release.set()
    thread = telemetry._producer_init_thread
    if thread is not None:
        thread.join(timeout=10)

    assert constructing.is_set(), "construction never started; the test patched the wrong thing"
    assert elapsed < 5, (
        f"the request path waited {elapsed:.1f}s on an unreachable broker; "
        "construction is no longer bounded"
    )


def test_a_failed_producer_construction_disables_telemetry_instead_of_raising(monkeypatch):
    """Construction that raises must leave telemetry off, not surface to the caller.

    The thread cannot propagate into the request that started it, so the only way a
    failure is visible is the flag it sets and the log it writes. A caller that saw
    an exception here would be a request failed by telemetry, which ADR 0001 forbids.
    """

    class _RefusesToConnect:
        def __init__(self, **kwargs):
            raise OSError("no route to broker")

    monkeypatch.setattr(kafka, "KafkaProducer", _RefusesToConnect)
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker.invalid:9092")
    monkeypatch.setattr(telemetry, "_producer", None)
    monkeypatch.setattr(telemetry, "_producer_init_failed", False)
    monkeypatch.setattr(telemetry, "_producer_init_thread", None)

    telemetry.publish_request_telemetry(
        method="GET", path="/health", status_code=200, latency_ms=0.5, code=None
    )

    thread = telemetry._producer_init_thread
    if thread is not None:
        thread.join(timeout=10)

    assert telemetry._producer is None
    assert telemetry._producer_init_failed is True


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
