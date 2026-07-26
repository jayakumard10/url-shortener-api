# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# git is required only to install the private agentic-events dependency below;
# the PAT is mounted as a BuildKit secret and the resulting git config is
# unset within this same layer so it never lands in the built image (same
# "never let the PAT land somewhere logs/layers could leak it" rule as
# locked decision 3's clone-per-run credential handling).
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=secret,id=github_pat \
    sh -c ' \
        if [ -f /run/secrets/github_pat ]; then \
            git config --global url."https://$(cat /run/secrets/github_pat)@github.com/".insteadOf "https://github.com/"; \
        fi && \
        pip install --no-cache-dir -r requirements.txt && \
        git config --global --unset url."https://$(cat /run/secrets/github_pat 2>/dev/null)@github.com/".insteadOf 2>/dev/null || true \
    '

COPY . .

EXPOSE 8000

CMD ["uvicorn", "url_shortener.main:app", "--host", "0.0.0.0", "--port", "8000"]
