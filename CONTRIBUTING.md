# Contributing

The rules this repository actually runs on are in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md). This file is the
practical version: how to get set up, what has to be true before you open a pull request,
and which parts of the tree will refuse a change that ignores them.

## Setup

```bash
python -m venv .venv && source .venv/Scripts/activate   # .venv/bin/activate on Linux/WSL
pip install -r requirements.txt
```

`requirements.lock` is the reproducible resolution — pinned versions plus hashes, with the
`agentic-events` git tag resolved to a commit SHA. Install from it when you need to match
CI exactly:

```bash
pip install --require-hashes -r requirements.lock
```

## Tests are in four tiers, and the directory is the marker

| Tier | Needs | Holds |
|---|---|---|
| `tests/unit/` | nothing outside the process | 21 tests |
| `tests/contract/` | nothing outside the process | what this service puts on the wire, and the layout itself |
| `tests/integration/` | a real engine, the ASGI stack | 17 tests |
| `tests/evaluation/` | a real Kafka broker | the telemetry seam |

**Put a new test in the tier it needs, not the tier its subject sounds like.** A test that
calls `create_engine` is integration however narrow its subject is — `test_repository.py`
sat in the wrong tier for months behind a docstring that claimed otherwise.

You do not write the marker. `tests/conftest.py` derives it from the parent directory, and
a test file outside the four tiers fails collection rather than quietly never running.
There is no way to add an unmarked test, which is deliberate: an unmarked test is counted
in "passed" and skipped by any filtered run.

```bash
pytest                                    # everything
pytest -m unit                            # one tier
pytest --cov=url_shortener --cov-report=term-missing --cov-fail-under=97   # what CI runs
```

The evaluation tier skips when no broker is reachable, so a plain `pytest` is clean on a
laptop with nothing started. To actually run it, start `agentic-sdlc-eventbus`'s compose
stack and then:

```bash
URL_SHORTENER_REQUIRE_BROKER=1 pytest tests/evaluation
```

That variable turns a skip into a failure. Use it whenever you have started a broker: a
skipped seam test proves nothing while looking green.

## Before you open a pull request

- **The suite is green by exit code.** `pytest` can print "47 passed" and exit 1, and
  `cmd | tail -1` returns `tail`'s status rather than `cmd`'s. Check `echo $?`.
- **Changed a dependency?** Regenerate the lock, or CI will tell you to:
  ```bash
  uv pip compile requirements.txt --universal --generate-hashes --python-version 3.12 -o requirements.lock
  ```
- **Changed the telemetry envelope?** That is a change to
  `url-shortener.request-telemetry.v1`, which other repositories read. The contract tier
  will tell you; do not weaken it to make it pass.
- **Changed the layout?** `tests/contract/test_repository_structure.py` asserts it. Either
  satisfy the assertion or change it deliberately, with the reasoning in the commit.
- **Documentation moves in the same commit** as whatever it describes. Stale docs are a
  bug, not a follow-up.

## Commits

Build one piece, test it against something real, commit it. A commit message that needs
"and" three times is more than one commit. No `Co-Authored-By` and no "Generated with"
trailers, in commits or PR bodies.

## Two things that will bite you

**Never rename a CI job.** Required status checks match a job's *display name*. The
required contexts on `main` are `test` and `compose-smoke-test`; renaming either leaves
branch protection waiting on a context nothing reports — every check green, the pull
request stuck at `BLOCKED`. If a rename is genuinely needed, update the ruleset in the
same change.

**Never commit anything under `secrets/`.** Only `.example` templates belong there.
`.gitignore` covers the ordinary case and the `secret-hygiene` job in `security.yml`
covers the one it cannot — a file added with `git add -f`, or one committed before the
rule existed.

## Something you cannot fix here

A broker outage must never turn a successful request into a failed one. Telemetry is
best-effort: unset configuration, an unreachable broker and a failed send are all skipped
and logged, never raised. Every path that touches the broker is bounded in time, and the
middleware publishes after the response is generated. This was violated once and hung
every request in the stack — see [`docs/adr/0001`](docs/adr/0001-bounded-background-producer-construction.md).
If a change makes a response wait on Kafka, it is wrong regardless of how green the suite is.
