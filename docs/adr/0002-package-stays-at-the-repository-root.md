# 0002: The package stays at the repository root

Date: 2026-08-31
Status: Accepted

## Context

The reference layout used by `agentic-sdlc-eventbus` puts its package under `src/`, ships a
`py.typed` marker, and declares a `[project]` table with a build backend. Adopting that shape
here was the obvious move during the repository restructure, and it is wrong for this
repository.

`src/` exists to solve one problem: stopping tests from importing the working tree when what
you actually want to exercise is the installed wheel. That problem requires a wheel. This
repository has none, and nothing installs it:

```
$ ls setup.py pyproject.toml setup.cfg
ls: cannot access 'setup.py': No such file or directory
ls: cannot access 'pyproject.toml': No such file or directory
ls: cannot access 'setup.cfg': No such file or directory

$ grep -rn "pip install" Dockerfile .github/workflows/ci.yml
Dockerfile:16:RUN pip install --no-cache-dir -r requirements.txt
.github/workflows/ci.yml:51:        run: pip install -r requirements.txt
```

Both install steps install *dependencies*, never this package. The container resolves
`url_shortener` because `WORKDIR /app` puts the working directory on `sys.path`:

```
Dockerfile:4   WORKDIR /app
Dockerfile:11  COPY requirements.txt .
Dockerfile:16  RUN pip install --no-cache-dir -r requirements.txt
Dockerfile:18  COPY . .
Dockerfile:22  CMD ["uvicorn", "url_shortener.main:app", ...]
```

Nor is there an external Python consumer. Grepping the four sibling repositories for
`url_shortener` returns exactly one hit, and it is a comment naming this repository's dev
API-key default in `agentic-sdlc-control-plane/scripts/demo-end-to-end.ps1`. Nothing imports
this package.

## Decision

The package stays at the repository root as `url_shortener/`.

- **No `src/` layout.** It would break the container build unless the application also began
  installing itself, which is ceremony an application does not need. It protects against a
  failure mode that cannot occur here.
- **No `[project]` table and no `[build-system]`.** `pyproject.toml` carries `[tool.*]`
  sections only — pytest and coverage configuration, consolidated from the `pytest.ini` and
  `.coveragerc` it replaced.
- **No `py.typed`.** A PEP 561 marker matters to a downstream `mypy` reading an installed
  distribution. There is no distribution and no downstream.
- **`requirements.txt` stays the install mechanism**, with `requirements.lock` supplying the
  reproducibility that pinning alone does not.

## Consequences

- The `Dockerfile` and `docker-compose.yml` were not touched by the restructure at all, so no
  part of it can affect the running service.
- The wheel-inspection step that a packaged repository needs — building and listing the
  archive to prove package data actually ships — does not apply here and was deliberately not
  invented.
- `agentic-sdlc-cobol-modernizer` genuinely is a distributable: it has a console-script entry
  point and ships package data. Its `src/` layout and `pyproject.toml` are correct **for it**.
  The two repositories differ because their situations differ, not because one is behind.
- The comment in `agentic-sdlc-control-plane`'s demo script that names `url_shortener/auth.py`
  by path stays valid. Under a `src/` move it would have gone stale in another repository, and
  nothing here would have caught it.
- **The general lesson:** a layout borrowed from a repository with a different job is
  cargo cult. `src/` is a good default for a library and a liability for an application, and
  the deciding question is not what the reference repository does but whether anything
  installs this one.
