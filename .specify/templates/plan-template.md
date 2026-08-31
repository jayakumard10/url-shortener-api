# Plan: [FEATURE NAME]

**Spec:** `specs/NNN-short-slug/spec.md` · **Status:** Draft | Approved | Implemented
**Created:** YYYY-MM-DD

> HOW. This is where file names, signatures and library choices belong. If the spec
> changed while writing this, change the spec — do not let the plan quietly redefine it.

---

## Constitution check

Which articles this touches, and how it satisfies each. An article this contradicts
does not get worked around here: it gets amended in `.specify/memory/constitution.md`,
with the reasoning, before this plan proceeds.

| Article | Touched? | How this satisfies it |
|---|---|---|
| I — tenant service, own database | | |
| II — a broker outage never reaches a user | | |
| III — the seam needs real verification | | |
| IV — layout enforced by a test | | |
| V — every claim needs a command | | |
| VI — application, package at root | | |
| VII — CI job names are contracts | | |
| VIII — small commits, docs in step | | |

## Approach

The shape of the change, and the alternative that was rejected. A plan with no rejected
alternative usually means only one was considered.

## Files

| File | Change | Why |
|---|---|---|

## Verification

What proves this works, per tier. Name the command, not the intention.

- **unit** —
- **contract** — would this break a consumer?
- **integration** —
- **evaluation** — from the real calling position, against a broker.

## Rollback

What undoes this if it lands badly, and what cannot be undone.
