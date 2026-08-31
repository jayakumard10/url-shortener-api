# Spec: [FEATURE NAME]

**Spec ID:** `NNN-short-slug` · **Status:** Draft | Approved | Implemented | Superseded
**Created:** YYYY-MM-DD

> **WHAT and WHY only.** No file names, no function signatures, no library choices —
> those belong in `plan.md`. A spec a reviewer cannot argue with, because it is already
> describing an implementation, is not doing its job.

---

## Problem

What is wrong today, stated so someone who has never opened this repository can tell
whether it matters. Prefer the observable failure over the abstraction.

## Evidence

How this was established. A command that was run, a file that was read, a defect that
occurred. Per Article V, a claim with nothing behind it does not go in a spec.

```
# the command, and enough of its output to be checked
```

## Who is affected

Callers of this service, consumers of `url-shortener.request-telemetry.v1`, or whoever
maintains this repository. Article II means a telemetry change can affect a user even
when it looks internal — say so if it does, and say why if it genuinely does not.

## Outcome

What is true when this is done, written so it can be verified rather than believed.

- [ ] …
- [ ] …

## Explicitly out of scope

What this deliberately does not do. A spec without this section grows one during
implementation.

## Risks

What breaks, and what the failure looks like from outside the process. Per Article III,
"the tests pass" is not an answer here.
