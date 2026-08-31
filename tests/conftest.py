"""Tier markers derived from the directory, and the shared database fixtures.

The fixtures live here at the tests/ root rather than under one tier because two
tiers need them: ``client`` is used by tests/integration/ and the tier directories
are siblings, so a fixture defined in one is not visible from the other.

Each fixture gives a test an isolated in-memory SQLite database, neutralizes the
app's real init_db() so tests never touch the production DATABASE_URL, and leaves
Kafka telemetry disabled (KAFKA_BOOTSTRAP_SERVERS unset) so tests never attempt a
real broker connection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from url_shortener import rate_limit
from url_shortener.db import Base, get_session
from url_shortener.main import app

REPO_ROOT = Path(__file__).resolve().parents[1]

TEST_API_KEY = "test-api-key"

TIERS = ("unit", "contract", "integration", "evaluation")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Give every test the tier marker for the directory it lives in, and refuse strays.

    A test with no marker is still collected and still counted in "passed" - it is
    only invisible to a marker-filtered run. So the day CI grows a ``-m`` selector,
    an unmarked file silently stops being executed while the run stays green, and
    the coverage floor quietly starts measuring a subset. ``--strict-markers`` does
    not catch this: it catches a *misspelled* marker, never a *missing* one.

    Deriving the marker from the parent directory means a new test file cannot
    forget one. The hard failure below means a test dropped outside the four tiers
    is a collection error rather than a test that never runs.
    """
    strays = []
    for item in items:
        tier = next((part for part in item.path.parts if part in TIERS), None)
        if tier is None:
            strays.append(str(item.path.relative_to(REPO_ROOT)))
            continue
        item.add_marker(getattr(pytest.mark, tier))

    if strays:
        raise pytest.UsageError(
            "these test files are not in a tier directory, so a marker-filtered run "
            f"would never execute them: {sorted(set(strays))}. "
            f"Move each into tests/{{{','.join(TIERS)}}}/."
        )


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(test_engine, monkeypatch):
    testing_session_local = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_get_session():
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
    monkeypatch.setattr("url_shortener.main.init_db", lambda: None)
    app.dependency_overrides[get_session] = override_get_session
    rate_limit.reset()
    with TestClient(app) as test_client:
        test_client.headers.update({"X-API-Key": TEST_API_KEY})
        yield test_client
    app.dependency_overrides.clear()
