# CLAUDE.md

Standing instructions for AI agents (and human contributors) working in this repository. Claude
Code auto-loads this file every session; it is committed so the process that produced this
repository is reproducible by anyone who clones it.

The three roles this file refers to are defined as executable agents in
[`.claude/agents/`](.claude/agents/).

## Commit discipline

- Build one small piece at a time: write it, test it against something real (not just "looks
  right"), and only once it passes, commit it. Never batch a large, untested pile of files into
  one commit at the end — that's exactly the failure mode this rule exists to prevent.
- Each commit should be small enough to describe honestly in its own message — if the message
  needs "and" three times, it's probably more than one commit.
- Author: Jayakumar Devaraj <jayakumar.d10@gmail.com>. Never add Co-Authored-By or "Generated
  with" trailers/footers of any kind.
- Fresh `git init` per repo, no monolith history preserved.

## Self-check before continuing

Periodically ask: "Has it been a while since my last commit, or have I built more than one
untested piece without committing?" If yes, stop and commit what already passes its own tests
before writing anything new — don't let uncommitted work pile up into a batch to sort out later.
This applies to every repo in this platform, checked regularly, not just at the end of a session.

## Keep documentation in sync

Whenever a plan or implementation changes — a design decision gets revised, a bug fix changes
behavior, a dependency pin changes — update the relevant documentation (README, this file, the
platform's planning document) in the same change, not as a follow-up. Stale docs are a bug, not
a TODO.

## Documentation standard

- README.md section order, fixed: Tech stack -> Architecture -> Quickstart -> Local development
  -> Testing -> Deployment/CI. Nothing else. README explains how to run/use this repo, never why
  a decision was made (that's ADRs, `docs/adr/`) or how this repo relates to the other repos in
  this platform split (tracked in a private planning document, not committed anywhere).
- Never reference local machine paths (`C:\Users\...`, `C:\srcCode\...`) in committed files.
- Every significant design decision gets a lightweight ADR: `docs/adr/NNNN-title.md` (Context /
  Decision / Consequences).
- A doc claim not backed by a command actually run against real containers/code is a bug, not
  documentation — verify before writing, not after.

## AI-assisted engineering practice

This platform demonstrates AI-assisted engineering across three roles per repo, scoped to what
actually applies:

1. **Design**: a design document and architecture diagram for this repo (README + this file).
2. **Development**: error handling and logging, auditing capabilities where relevant, meaningful
   Git commit history (see above).
3. **QA**: unit tests + coverage report, and/or a functional verification report for anything a
   unit test can't reach (e.g. real broker/container behavior).

## This repo's place in the platform

FastAPI URL shortener — the one repo in this platform split that is a tenant service, not part of
the `agentic-sdlc-*` platform brand (deliberately unprefixed for that reason). It produces
`request-telemetry` events and is the target of the platform's clone-per-run git operations; it
has no knowledge of and no dependency on any other repo's internals beyond the shared
`agentic-events` envelope contract.
