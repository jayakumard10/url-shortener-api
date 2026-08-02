"""FastAPI entry point: the URL shortener's core APIs, analytics, and reliability feature."""

from __future__ import annotations

import secrets
import string
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from url_shortener import rate_limit, telemetry
from url_shortener.auth import require_api_key
from url_shortener.db import get_session, init_db
from url_shortener.repository import SQLAlchemyURLRepository, URLRepository
from url_shortener.schemas import ShortenRequest, ShortenResponse, StatsResponse

_CODE_ALPHABET = string.ascii_letters + string.digits
_CODE_LENGTH = 7
_MAX_CODE_GENERATION_ATTEMPTS = 10


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="URL Shortener", lifespan=lifespan)


@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = (time.perf_counter() - start) * 1000
    code = request.path_params.get("code") if request.path_params else None
    telemetry.publish_request_telemetry(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        latency_ms=latency_ms,
        code=code,
    )
    return response


def get_repository(session: Session = Depends(get_session)) -> URLRepository:
    return SQLAlchemyURLRepository(session)


def _generate_unique_code(repo: URLRepository) -> str:
    for _ in range(_MAX_CODE_GENERATION_ATTEMPTS):
        candidate = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        if not repo.code_exists(candidate):
            return candidate
    raise HTTPException(status_code=500, detail="failed to generate a unique short code")


@app.get("/health")
def health() -> dict[str, object]:
    """Liveness, plus whether telemetry is actually reaching the broker.

    Telemetry failures never fail a request, so they are silent by design. Carrying
    the counter here is what makes them countable from outside the process without
    giving up that property.
    """
    return {"status": "ok", "telemetry": telemetry.telemetry_status()}


@app.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
def shorten(
    payload: ShortenRequest,
    request: Request,
    repo: URLRepository = Depends(get_repository),
) -> ShortenResponse:
    client_key = request.client.host if request.client else "unknown"
    if not rate_limit.is_allowed(client_key):
        raise HTTPException(status_code=429, detail="rate limit exceeded, try again later")

    code = _generate_unique_code(repo)
    long_url = str(payload.long_url)
    repo.create(code=code, long_url=long_url)
    return ShortenResponse(code=code, short_url=f"/{code}", long_url=long_url)


@app.get(
    "/{code}/stats",
    response_model=StatsResponse,
    dependencies=[Depends(require_api_key)],
)
def stats(code: str, repo: URLRepository = Depends(get_repository)) -> StatsResponse:
    record = repo.get_by_code(code)
    if record is None:
        raise HTTPException(status_code=404, detail="short URL not found")
    return StatsResponse(
        code=record.code,
        long_url=record.long_url,
        click_count=record.click_count,
        created_at=record.created_at,
    )


@app.get("/{code}")
def redirect(code: str, repo: URLRepository = Depends(get_repository)) -> RedirectResponse:
    record = repo.get_by_code(code)
    if record is None:
        raise HTTPException(status_code=404, detail="short URL not found")
    repo.increment_click(code)
    return RedirectResponse(url=record.long_url, status_code=307)
