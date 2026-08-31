# Tasks: The repository has a deliberate structure

**Spec:** `specs/001-repository-structure/spec.md` · **Plan:** `specs/001-repository-structure/plan.md`

> One commit per task, each tested against something real before committing.
> All tasks below are complete; the commit subject for each is given.

---

## Layout moves

- [x] **T001** — Move the four no-I/O test files into `tests/unit/`.
  - Verify: 38 passed, exit 0, coverage 98%
  - Commit: `Move the no-I/O tests into a unit tier`

- [x] **T002** — Move the two engine-backed files into `tests/integration/`; correct
      `test_repository.py`'s docstring, which claimed "Unit tests" directly above a
      `create_engine` call.
  - Verify: 38 passed, exit 0
  - Commit: `Move the tests that need a real engine into an integration tier`

- [x] **T003** — Split the one client-driven test out of `unit/test_telemetry.py`.
  - Verify: 21 unit + 17 integration, the same 38 tests as before
  - Commit: `Split the client-driven telemetry test out of the unit tier`

- [x] **T004** — Derive tier markers from the directory in `conftest.py`; register them.
  - Verify: `-m unit` selects 21 and `-m integration` selects 17; a stray probe file
    fails collection at exit 4 and names itself in the error
  - Commit: `Derive each test's tier marker from its directory`

- [x] **T005** — Add the contract tier.
  - Verify: 8 passed; mutation probes — a renamed metrics key, an undeclared envelope
    field, a dropped partition key — fail 1, 8 and 1 tests respectively
  - Commit: `Add a contract tier asserting what this service puts on the wire`

- [x] **T006** — Add the evaluation tier; move the README's verification prose into
      `REPORT.md`.
  - Verify: 1 passed against a live broker; skips at exit 0 without one; fails when
    `URL_SHORTENER_REQUIRE_BROKER=1` promised one
  - Commit: `Add an evaluation tier that consumes the event back off a real broker`

## Tooling and gates

- [x] **T007** — Fold `pytest.ini` and `.coveragerc` into `pyproject.toml`.
  - Verify: pytest reports `configfile: pyproject.toml`, collects 47, registers four
    markers with no unknown-marker warnings; bare `coverage run` still scoped to
    `url_shortener`
  - Commit: `Fold pytest.ini and .coveragerc into a pyproject.toml`

- [x] **T008** — Generate `requirements.lock`; gate its currency in CI.
  - Verify: recompiles byte-identical (exit 0); one changed pin is detected (exit 1)
  - Commit: `Lock the dependency resolution and gate it in CI`

- [x] **T009** — Ignore `.env` and `docker-compose.override.yml`.
  - Verify: both created, both ignored by git, both removed
  - Commit: `Stop compose's silent local overrides from ever being committed`

- [x] **T010** — Add `CODEOWNERS` and `dependabot.yml`.
  - Verify: both parse as YAML
  - Commit: `Add CODEOWNERS and Dependabot for the three ecosystems present`

- [x] **T011** — Add `security.yml`.
  - Verify: parses, carries no paths filter; `pip-audit` run locally and reports two
    real advisories; the secret guard verified in both directions
  - Commit: `Add a security workflow: dependency CVEs, secret hygiene, CodeQL`

## Documents

- [x] **T012** — Constitution and three templates.
  - Commit: `Write down the non-negotiables as a constitution and three templates`

- [x] **T013** — This spec, plan and task list.
  - Commit: `Record how this layout arrived as spec 001`

- [x] **T014** — ADR 0002 (package at root) and ADR 0003 (layout enforced by a test).
  - Commit: `Record the package-location and enforced-layout decisions as ADRs`

- [x] **T015** — `CONTRIBUTING.md` and `SECURITY.md`.
  - Commit: `Add contributing and security-policy documents`

- [x] **T016** — Reorder the README to the section order CLAUDE.md already mandated, and
      refresh the coverage table that the new tiers changed.
  - Commit: `Put the README in the section order CLAUDE.md already required`

## Enforcement, last

- [x] **T017** — `tests/contract/test_repository_structure.py`.
  - Verify: passes on the tree as built; assertions shown to fail when their subject is
    removed
  - Commit: `Enforce the repository layout with a test`

## Order

Layout moves first, so `git mv` keeps history attached to the files. The marker hook only
after every test is already in a tier, because it fails collection on a stray. The
structure test last, so it encodes what was built rather than what was planned.

## Done means

- [x] Every task above is a separate commit.
- [x] The suite is green by exit code, not by a summary line.
- [x] Documentation changed in the same commit as the content it describes.
- [x] Everything found and deliberately not fixed is written down in `plan.md`.
