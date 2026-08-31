# Spec: The repository has a deliberate structure

**Spec ID:** `001-repository-structure` · **Status:** Implemented
**Created:** 2026-08-31

> **Provenance, so this is not mistaken for something it is not.** This spec was written
> during the work it describes, not before it. The engagement began as an audit of the
> existing tree, and the audit's findings became these documents. Writing it as though it
> had been specified in advance would be manufacturing a record that did not exist — the
> same reason `AGENTS.md` says what it says about the agent definitions. What is
> reproducible is the reasoning and the verification, not a prior planning session.

---

## Problem

The repository had 34 files in a layout nobody had decided on. Individually every file
was fine; collectively there was no way for a new contributor to tell which parts of the
tree were deliberate and which were where they landed. Three consequences were real
rather than stylistic:

1. **Nothing verified the one thing this service can break for another repository.** It
   publishes `url-shortener.request-telemetry.v1`, and no test anywhere checked that the
   envelope it builds is one a consumer can parse.
2. **No test carried a tier marker.** Harmless while CI runs the suite unfiltered, and a
   silent trap the moment anything adds a `-m` selector: unmarked tests are collected,
   counted in "passed", and never executed by the filtered run.
3. **The structure was documented nowhere and enforced by nothing**, so every later
   change would negotiate it again.

## Evidence

The tree, and the absence of markers:

```
$ git ls-files | wc -l
34

$ grep -rn "pytest.mark\|markers" tests/ pytest.ini
(no output)
```

Nothing installs this repository, so it is an application rather than a library — which
decides where the package belongs:

```
$ ls setup.py pyproject.toml setup.cfg
ls: cannot access 'setup.py': No such file or directory
ls: cannot access 'pyproject.toml': No such file or directory
ls: cannot access 'setup.cfg': No such file or directory

$ grep -rn "pip install" Dockerfile .github/workflows/ci.yml
Dockerfile:16:RUN pip install --no-cache-dir -r requirements.txt
.github/workflows/ci.yml:51:        run: pip install -r requirements.txt
```

Baseline before any change, by exit code rather than by summary line:

```
$ pytest --cov=url_shortener --cov-report=term-missing -q; echo $?
38 passed
TOTAL  241  6  98%
0
```

## Who is affected

- **Consumers of `url-shortener.request-telemetry.v1`** — the drift metrics in
  `agentic-sdlc-mlops` and the platform's readers. They were exposed to an unverified
  envelope.
- **Anyone contributing here**, who had no way to distinguish the deliberate parts of
  the tree from the accidental ones.
- **No external Python importer.** Grepping the four sibling repositories for
  `url_shortener` returns one hit, a comment in
  `agentic-sdlc-control-plane/scripts/demo-end-to-end.ps1` naming this repo's dev API-key
  default. Nothing imports this package, which is what makes Article VI available.

## Outcome

- [x] Every test lives in one of four tier directories, and its marker is derived from
      that directory rather than written by hand.
- [x] A contract tier asserts what this service puts on the wire, shown to fail when the
      envelope changes.
- [x] An evaluation tier consumes a published event back off a real broker.
- [x] Tool configuration is in one `pyproject.toml` with no `[project]` table.
- [x] The dependency resolution is locked and the lock's currency is gated in CI.
- [x] The non-negotiables are written down and the layout is enforced by a test.
- [x] Governance files exist: `CONTRIBUTING.md`, `SECURITY.md`, `CODEOWNERS`,
      `dependabot.yml`, a security workflow.

## Explicitly out of scope

- **Application behaviour.** No route, no auth rule, no rate-limiting change. Moving a
  file was in scope; changing what it does was not.
- **Dependency upgrades.** `pip-audit` reports two real advisories and both were left
  alone deliberately — see `plan.md`.
- **A `src/` move or packaging.** Article VI, `docs/adr/0002`.
- **Renaming CI jobs.** Article VII.
- **`LICENSE`.** The owner's decision, not this engagement's.

## Risks

- **Test moves break import paths.** `pythonpath` had to survive the `pytest.ini` →
  `pyproject.toml` fold, or all 38 tests fail at collection.
- **The coverage floor could silently measure a subset.** Adding markers makes a `-m`
  selector possible; a future CI change that filters without adjusting `--cov-fail-under`
  would ratchet the floor down against a smaller suite. The floor is unchanged here and
  the whole suite still runs.
- **A renamed CI job would leave branch protection waiting on a context nothing
  reports** — every check green and the PR stuck. Neither job was renamed.
- **The evaluation tier depends on a broker that CI does not start.** It skips rather
  than fails, so the tier adds no signal in CI today. Stated rather than hidden; see
  `plan.md`.
