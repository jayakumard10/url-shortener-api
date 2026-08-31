# Tasks: [FEATURE NAME]

**Spec:** `specs/NNN-short-slug/spec.md` · **Plan:** `specs/NNN-short-slug/plan.md`

> One commit per task, in this order. Each is written, tested against something real,
> then committed — never batched. A task whose description needs "and" three times is
> more than one task.

---

## Tasks

- [ ] **T001** — …
  - Verify: `…`
  - Commit: `…`

- [ ] **T002** — …
  - Verify: `…`
  - Commit: `…`

## Order

Why this order and not another. Layout moves go first so history follows the files;
anything that *enforces* structure goes last, so it encodes what was actually built
rather than what was planned.

## Done means

- [ ] Every task above is committed separately.
- [ ] The suite is green by **exit code**, not by a summary line.
- [ ] Documentation changed in the same commits as the behaviour it describes.
- [ ] Anything found and deliberately not fixed is written down.
