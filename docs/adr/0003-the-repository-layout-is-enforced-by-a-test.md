# 0003: The repository layout is enforced by a test

Date: 2026-08-31
Status: Accepted

## Context

Before the 2026-08-31 restructure this repository had 34 files in a layout nobody had
decided on. Each file was individually reasonable; collectively there was no way to tell
which parts of the tree were deliberate and which were simply where something landed. A
README can describe a structure, but a described structure is a suggestion — the next
contributor inherits a tree that is *mostly* the documented one and no way to tell which
deviations were choices.

One specific failure mode made this concrete rather than theoretical. No test in the
repository carried a tier marker:

```
$ grep -rn "pytest.mark\|markers" tests/ pytest.ini
(no output)
```

That was harmless only because CI happened to run the suite unfiltered. A test with no
marker is still collected, still counted in "passed", and completely skipped by any
marker-filtered run. `--strict-markers` does not catch it: that flag catches a
*misspelled* marker, never a *missing* one. The same defect in `agentic-sdlc-eventbus`
silently disabled 18 tests and dropped a module to 69% coverage while the run printed
"99 passed".

Convention does not survive contact with a hurry. Only an assertion does.

## Decision

The layout is asserted by `tests/contract/test_repository_structure.py`, and tier markers
are derived from the directory in `tests/conftest.py` rather than written by hand.

The structure test asserts **shape, never content**. It does not care what an ADR argues,
only that decisions are recorded as ADRs and numbered without gaps; not what a spec says,
only that specs carry the sections the workflow depends on. Specifically: the package is
where this repository decided it goes and is not also somewhere else, every test lives in
a tier directory, all four tiers exist and are non-empty, the evaluation tier carries its
report, ADRs are numbered contiguously, spec directories are complete, and the required
root and workflow files exist.

It is in the contract tier because that is what it is: a change that breaks it is a change
to what this repository promises about itself.

The `conftest.py` hook is the other half. It assigns each test the marker for its parent
directory and raises a `pytest.UsageError` for anything outside the four tiers, so a stray
file is a collection error rather than a test that quietly never runs. `--strict-markers`
is also enabled — the two catch different halves of the same problem and neither
substitutes for the other.

The structure test was written **last**, after every move was made. A structure test
written first is a wish list, and the temptation is then to bend the tree to satisfy it
rather than to assert what was actually built.

## Consequences

- A layout change now either satisfies a specific assertion or has to argue with it. That
  is the point: the argument becomes explicit rather than a silent drift.
- Both halves were verified against real breakage rather than assumed to work. A probe
  file dropped at the `tests/` root fails collection at exit 4 and names itself; marker
  selection splits the suite exactly along the directories.
- The test encodes decisions specific to this repository and must not be copied wholesale
  into another. Its package-location assertion is the inverse of `agentic-sdlc-eventbus`'s
  — it asserts the package is at the root and *not* under `src/`, for the reasons in
  ADR 0002. Copying that repository's version here would have asserted the opposite of
  what this repository decided.
- Adding a fifth tier, a new required root file, or a new workflow means updating this
  test in the same change. That is friction, and it is the intended kind: it is what makes
  the tree a decision rather than a residue.
