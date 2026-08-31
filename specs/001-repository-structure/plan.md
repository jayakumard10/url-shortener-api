# Plan: The repository has a deliberate structure

**Spec:** `specs/001-repository-structure/spec.md` · **Status:** Implemented
**Created:** 2026-08-31

---

## Constitution check

| Article | Touched? | How this satisfies it |
|---|---|---|
| I — tenant service, own database | No | No change to Postgres, routes or ownership. |
| II — a broker outage never reaches a user | Yes | No production telemetry code changed. The evaluation tier waits for a ready producer rather than weakening the 1s join bound that makes the guarantee hold. |
| III — the seam needs real verification | Yes | This is where the evaluation tier came from; it publishes and consumes against a live broker. |
| IV — layout enforced by a test | Yes | The article exists because of this work. `tests/contract/test_repository_structure.py` lands last, so it encodes what was built. |
| V — every claim needs a command | Yes | Every commit message carries the command and exit code. Contract tests were mutation-probed; the secret guard and lock gate were run in both directions. |
| VI — application, package at root | Yes | Confirmed by evidence, recorded in ADR 0002, asserted by the structure test. |
| VII — CI job names are contracts | Yes | Required contexts read from the live ruleset before touching a workflow. Neither renamed. `security.yml` is added but not required and not path-filtered. |
| VIII — small commits, docs in step | Yes | One commit per piece; README updated in the same commit as the content that moved. |

## Approach

Audit first and change nothing until the tree is understood, then move files before
creating any, then let the enforcing test land last.

**The order matters and is not arbitrary.** Layout moves come first so `git mv` keeps
history attached to the files. The marker hook can only be added once every test is
already in a tier, because it fails collection on a stray. The structure test comes last
so it asserts what was actually built — a structure test written first is a wish list,
and the temptation is then to bend the build to it.

**Rejected: adopting the reference layout wholesale.** `agentic-sdlc-eventbus` is the
worked example, and copying it would have brought `src/`, `py.typed`, a `[project]`
table and `uv.lock`. Each is right there and wrong here, because that repository is a
library three repos install and this one is an application nothing installs. Every
retracted item was retracted with a reason in the audit rather than silently omitted.

**Rejected: registry-backed schema validation in the contract tier.** The intended test
was to validate the envelope against `agentic_events.registry`. `requirements.txt` pins
`agentic-events` at `v0.1.0`, which ships `envelope.py` alone — no registry module and
no per-topic JSON Schema:

```
$ python -c "from agentic_events import registry"
ImportError: cannot import name 'registry' from 'agentic_events'
```

Bumping that pin is a dependency change, not a structural one. `EventEnvelope` is
declared `extra="forbid"`, which is enough to reject an invented field, so the contract
tier validates against the installed model and the file is named for what it asserts.
**Follow-up:** bump the pin, then validate against the registry's schema.

## Files

| File | Change | Why |
|---|---|---|
| `tests/{unit,contract,integration,evaluation}/` | NEW | Tier directories; markers derive from them. |
| `tests/test_*.py` | MOVE | Six files into tiers by what each needs, not by what its docstring claimed. |
| `tests/conftest.py` | EDIT | `pytest_collection_modifyitems` derives markers, raises on strays. Fixtures stay at the `tests/` root because two tiers need them. |
| `tests/contract/test_envelope_contract.py` | NEW | The wire form a consumer parses. |
| `tests/evaluation/test_event_reaches_the_broker.py` | NEW | Publish and consume against a real broker. |
| `tests/evaluation/REPORT.md` | NEW | The verification record, moved out of the README. |
| `tests/contract/test_repository_structure.py` | NEW | Enforces the above. Lands last. |
| `pyproject.toml` | NEW | `[tool.*]` only. Replaces `pytest.ini` and `.coveragerc`. |
| `requirements.lock` | NEW | Resolves the `v0.1.0` tag to a commit SHA; hashes every wheel. |
| `.github/workflows/ci.yml` | EDIT | Lock-currency gate added to the existing `test` job. No rename. |
| `.github/workflows/security.yml` | NEW | pip-audit, secret hygiene, CodeQL. Not required, not path-filtered. |
| `.github/CODEOWNERS`, `.github/dependabot.yml` | NEW | Ownership; three ecosystems. |
| `.gitignore` | EDIT | `.env` and `docker-compose.override.yml`, which compose merges silently. |
| `docs/adr/0002-*.md`, `docs/adr/0003-*.md` | NEW | The package-location and enforced-layout decisions. |
| `README.md` | EDIT | Reordered to the section order CLAUDE.md already mandated. |
| `CONTRIBUTING.md`, `SECURITY.md` | NEW | Public repo with an API-key model and a `secrets/` directory. |
| `Dockerfile`, `docker-compose.yml`, `secrets/`, `url_shortener/` | UNTOUCHED | Article VI, and the rule that nothing under `secrets/` moves during a structural change. |

## Verification

- **unit** — `pytest -m unit` selects 21, matching the directory.
- **contract** — 8 passed, and shown to fail: renaming a metrics key, adding an
  undeclared envelope field, and dropping the partition key produced 1, 8 and 1 failures
  respectively, with the source restored after each probe.
- **integration** — 17 passed.
- **evaluation** — `URL_SHORTENER_REQUIRE_BROKER=1 pytest tests/evaluation` gave 1 passed
  against the eventbus broker on `localhost:9092`. The gate was checked both ways: it
  skips at exit 0 with no broker, and fails when one was promised.
- **gates** — the lock recompiles byte-identical, and a single changed pin is caught.
  The secret guard passes clean and catches a force-added password file.

## Known gaps, stated rather than left to be found

- **The evaluation tier does not run in CI.** No workflow starts a broker, so it skips
  and contributes no CI signal today. Wiring it up means a broker service in the
  workflow with `URL_SHORTENER_REQUIRE_BROKER=1`; that is a CI capability change and was
  left out of a layout engagement.
- **`pip-audit` is red on two real advisories** — `python-dotenv` 1.0.1
  (PYSEC-2026-2270) and `pytest` 8.3.4 (PYSEC-2026-1845). Not fixed here, because
  upgrading a dependency is not restructuring. `python-dotenv` is additionally never
  imported anywhere in the tree and looks removable outright.
- **A Dependabot PR will fail the lock gate** until the lock is regenerated. Documented
  in `dependabot.yml` with the command.
- **`telemetry.py`'s `REPO_URL` and `requirements.txt`'s git URL both use the old
  `jayakumard10` account name**, which now redirects to `jayakumar-devaraj`. They work,
  and the stale URL ships in every event's `git_target`.

## Rollback

Every commit is independent and revertable. The layout moves are `git mv`, so a revert
restores paths with history intact. Nothing in `url_shortener/`, the `Dockerfile`,
`docker-compose.yml` or `secrets/` was touched, so no rollback can affect the running
service. The one irreversible act would have been renaming a CI job, and none was
renamed.
