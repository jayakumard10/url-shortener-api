# syntax=docker/dockerfile:1
FROM python:3.14-slim

WORKDIR /app

# git is required only to resolve the agentic-events git dependency below. It is a
# build-only need; nothing in this service shells out to git at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# agentic-events resolves over anonymous HTTPS. This build previously mounted a PAT
# as a BuildKit secret because agentic-sdlc-eventbus was private; it is public now,
# so the credential - and the layer-scoped unset that kept it out of the image - is
# no longer needed. No build argument here is sensitive.
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "url_shortener.main:app", "--host", "0.0.0.0", "--port", "8000"]
