"""Publishes request telemetry to Kafka after each response is generated.

Every request gets an event, not just DB-mutating ones - the platform's drift
metrics (status-code distribution, 404-on-redirect rate, rate-limit-rejection
rate) need coverage of failed and rejected requests too, not only successful
shortens. Publishing is best-effort and must never block or fail the HTTP
response: if KAFKA_BOOTSTRAP_SERVERS is unset or the broker is unreachable,
telemetry is silently disabled rather than raising - see the master plan doc's
Reliability section ("Kafka down at produce time in Repo 4").
"""

from __future__ import annotations

import logging
import os
import socket
import threading
from datetime import datetime, timezone
from uuid import uuid4

from agentic_events import EventEnvelope, GitTarget, Producer

logger = logging.getLogger(__name__)

TOPIC = "url-shortener.request-telemetry.v1"
SERVICE_NAME = "url-shortener-api"
REPO_URL = "https://github.com/jayakumard10/url-shortener-api.git"

# How long a request will wait for Kafka producer construction to resolve
# before giving up on telemetry for *this* request. Construction keeps running
# in the background regardless, so this only bounds worst-case added latency
# on the first request(s) while the broker connection is being established -
# it does not retry-loop or block indefinitely if the broker is unreachable.
_PRODUCER_INIT_JOIN_TIMEOUT_S = 1.0

_instance_id = socket.gethostname()
_producer = None
_producer_init_failed = False
_producer_init_thread: threading.Thread | None = None
_producer_init_lock = threading.Lock()
publish_failures = 0


def _construct_producer(bootstrap_servers: str) -> None:
    global _producer, _producer_init_failed
    try:
        from kafka import KafkaProducer

        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: v.encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
            # Explicit api_version skips a live-connection protocol probe at
            # construction time; max_block_ms bounds how long a later .send()
            # can block on stale/missing metadata. Both exist specifically so
            # an unreachable broker degrades this repo's request latency
            # instead of hanging it - see the middleware hang this fixed.
            api_version=(2, 5, 0),
            request_timeout_ms=2000,
            max_block_ms=2000,
            retries=3,
        )
    except Exception:
        logger.exception("failed to initialize Kafka producer; request telemetry disabled")
        _producer_init_failed = True
        return
    _producer = producer


def _get_producer():
    global _producer_init_thread, _producer_init_failed

    if _producer is not None or _producer_init_failed:
        return _producer

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    if not bootstrap_servers:
        _producer_init_failed = True
        logger.info("KAFKA_BOOTSTRAP_SERVERS not set; request telemetry disabled")
        return None

    with _producer_init_lock:
        if _producer_init_thread is None:
            _producer_init_thread = threading.Thread(
                target=_construct_producer, args=(bootstrap_servers,), daemon=True
            )
            _producer_init_thread.start()

    _producer_init_thread.join(timeout=_PRODUCER_INIT_JOIN_TIMEOUT_S)
    return _producer


def _on_send_error(exc: BaseException) -> None:
    global publish_failures
    publish_failures += 1
    logger.warning("request telemetry publish failed: %s", exc)


def build_envelope(
    *,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    code: str | None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        correlation_id=str(uuid4()),
        service=SERVICE_NAME,
        event_type="request-telemetry",
        timestamp=datetime.now(timezone.utc),
        producer=Producer(service=SERVICE_NAME, instance_id=_instance_id),
        git_target=GitTarget(repo_url=REPO_URL, branch=os.environ.get("GIT_BRANCH", "main")),
        # [ASSUMPTION] every event from this repo is "brownfield" - it's raw
        # telemetry from an already-deployed service, never a fresh scaffold.
        scenario_type="brownfield",
        metrics={
            "status_code": status_code,
            "latency_ms": latency_ms,
            "is_404": status_code == 404,
            "is_rate_limited": status_code == 429,
        },
        payload={"method": method, "path": path, "code": code},
    )


def publish_request_telemetry(
    *,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    code: str | None,
) -> None:
    producer = _get_producer()
    if producer is None:
        return

    envelope = build_envelope(
        method=method, path=path, status_code=status_code, latency_ms=latency_ms, code=code
    )
    try:
        future = producer.send(TOPIC, key=code, value=envelope.model_dump_json())
        future.add_errback(_on_send_error)
    except Exception as exc:  # pragma: no cover - defensive, mirrors add_errback path
        _on_send_error(exc)
