"""The telemetry middleware, exercised through a real request rather than in isolation.

Integration rather than unit: this drives the app's whole middleware stack against a
live TestClient and SQLite, which is what makes it able to catch a {code} path param
that resolves in build_envelope but not in the middleware. The rest of telemetry.py is
unit-tested against a fake producer in tests/unit/test_telemetry.py.
"""

from __future__ import annotations


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
