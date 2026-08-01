# AGENTS.md

How to work on this repository with an AI coding agent, and how to check the agent is bound by
this repository's rules rather than its own defaults.

| File | Holds |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Standing instructions: commit discipline, documentation standard, this repo's place in the platform |
| [`.claude/agents/design.md`](.claude/agents/design.md) | README architecture, telemetry design and ADRs. Read-only over the source tree |
| [`.claude/agents/development.md`](.claude/agents/development.md) | Changes to `url_shortener`. Carries the rule that telemetry must never fail a request |
| [`.claude/agents/qa.md`](.claude/agents/qa.md) | Tests, coverage, and Docker Compose integration verification |

This is a **tenant service**, not part of the `agentic-sdlc-*` platform — deliberately unprefixed
for that reason. It produces `request-telemetry` events and is the target of the platform's
clone-per-run operations. It has no knowledge of any other repo's internals beyond the shared
`agentic-events` envelope.

## Provenance — read this before trusting the rest

**These definitions were written on 2026-07-31, after the implementation they describe.**
`git log -- .claude/` shows that, and it should. This service was built through interactive
sessions against `CLAUDE.md`; no prompt chain was ever stored, and reconstructing one now would be
manufacturing an audit trail that did not exist. **What is reproducible is the rules and the
workflow below — not the original sessions.**

## Invoking an agent

Claude Code resolves `.claude/agents/` from the repository root, so run from the repo:

```bash
claude --agent development -p "your task here"
```

### Check the binding actually worked

Ask for the rule this repo learned the hard way:

```bash
claude --agent development -p "In under 40 words: what must never happen to an HTTP response here, and why?"
```

Verified 2026-08-01, this returns ADR 0001's rule rather than generic error-handling advice:

> An HTTP response must never fail or hang due to telemetry (Kafka) issues — producer construction
> once blocked every request indefinitely when the broker was down, so telemetry failures must only
> log, never affect the response.

A generic answer about handling exceptions means the agent did not load.

## Which agent for which task

| Task | Agent | Why |
|---|---|---|
| Add a route | `development`, then `qa` | Telemetry is middleware, so a new route gets it for free — do not add per-route publishing that would cover only the success path |
| Add any external dependency | `development` | It inherits ADR 0001's rule: bound it, background it, and make its failure a log line rather than a status code |
| Change the telemetry contract | `design` | The metrics downstream drift detection consumes are the contract, and the README records it |
| Add tests | `qa` | Knows that a path never configured in tests has no coverage whatever the percentage says |

## What these agents do not do

- **They do not assume the happy path proves reliability.** A claim that a failure is tolerated is
  verified by *causing* that failure — the producer-hang defect was found by running the real stack
  with the broker deliberately stopped, not by asserting success.
- **They do not reach outside this service.** No agent here should encode how the control plane
  consumes what this service emits; that coupling is what the repository split exists to prevent.
