# SDD (Specification-Driven Development) Conventions

Before implementing any non-trivial feature, a Software Design Document (SDD) is written and
reviewed. Code is written to satisfy the spec, not the other way around.

---

## When an SDD Is Required

| Condition | SDD required? |
|---|---|
| Issue labeled `size:L` | Yes |
| Issue touches ≥ 2 top-level modules (`core/`, `views/`, `auth/`, `adapters/`) | Yes |
| Issue adds or changes public API surface (`__init__.py` exports) | Yes |
| Issue introduces a new domain (new module/package) | Yes |
| Issue labeled `size:S` or `size:M`, single module | No (BDD scenarios in issue body are sufficient) |
| Bug fix | No |

If in doubt, write the SDD. It takes less time than a misimplemented feature.

---

## SDD Location

Store SDDs in `docs/specs/`:

```
docs/specs/
├── TEMPLATE.md            # Canonical template (see below)
├── auth-end-to-end.md     # Example: feat(auth) end-to-end wiring
├── zero-config-admin.md   # Example: feat(core) zero-config admin
└── ...
```

File naming: `{kebab-case-feature-slug}.md`

UI/frontend design documents go in `docs/design/` (existing convention).
Implementation/backend SDDs go in `docs/specs/`.

SDDs are developer-only documents — they are NOT published to the docs site (`zensical.toml`).
They are consumed by agents and reviewers directly from the repository.

---

## SDD Template

Every SDD must use this structure. Omit a section only if it genuinely does not apply —
note the omission and why.

```markdown
# SDD: {Feature Title}

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft / In Review / Approved (architect) / Superseded |
| Issue | #{github-issue-number} |
| Milestone | {v0.x.y — Title} |
| Created | {YYYY-MM-DD} |
| Last updated | {YYYY-MM-DD} |

---

## Problem

What problem are we solving? Why now? What breaks or is missing without this?

## Goals

- Bullet list of outcomes this SDD achieves.

## Non-Goals

- Bullet list of what is explicitly out of scope (prevents scope creep).

## BDD Scenarios

Paste the scenarios from the GitHub issue here. The SDD and issue scenarios must stay in sync.

\`\`\`
Scenario: ...
  Given ...
  When  ...
  Then  ...
\`\`\`

## Design

### Architecture

Which modules are affected? Which new modules are created? How do they interact?
Include a dependency flow diagram if the change touches ≥ 3 modules.

### Data Model Changes

List any new or changed SQLModel/Pydantic models. Include field names, types, constraints.
If no changes: "No data model changes."

### API / Protocol Changes

List any new or changed endpoints, function signatures, or protocol methods.
If no changes: "No API changes."

### Configuration Changes

New parameters added to `Admin()`, `AdminOptions`, or env vars.
If no changes: "No configuration changes."

## Edge Cases & Error Handling

List failure modes, boundary conditions, and how each is handled.

## Migration & Backward Compatibility

- Is this a breaking change? (requires semver major bump)
- What migration steps are needed for existing users?
- If no breaking changes: "Backward compatible — no migration required."

## Open Questions

Questions that must be resolved before implementation starts. The architect agent resolves them
and moves each one into the Decision Log before setting "Approved (architect)".

## Decision Log

Record decisions made and why (including rejected alternatives):

| Decision | Rationale | Alternatives considered |
|---|---|---|
| | | |
```

---

## SDD Lifecycle

```
Draft → In Review → Approved → (implementation begins) → Superseded (if replaced)
```

1. **Draft**: Planning agent writes the SDD as part of epic creation.
2. **In Review**: The architect agent (`.claude/agents/software-architect.md`, autopilot job
   `approve-sdd`) reviews the SDD on the epic branch: runs the checklist below, resolves the Open
   Questions with the decision ladder, fills the Decision Log.
3. **Approved (architect)**: The architect agent approves and commits the SDD on the epic branch.
   Implementation sub-tasks are unblocked. The owner can veto on the epic PR, where the SDD change
   is part of the diff.
4. **Superseded**: If design changes significantly mid-implementation, update the SDD and note the change in the Decision Log.

The architect escalates to the owner (`needs-human` on the spec issue, with the exact question)
only when the design needs a breaking public API change, a new runtime dependency or a changed
runtime dependency floor, or a data-model migration. In that case the SDD stays `In Review`.

An SDD in `Draft` or `In Review` status BLOCKS implementation sub-tasks.
The implementation sub-task description MUST link to the SDD: `Spec: docs/specs/{slug}.md`.

---

## Planning Agent Rules

When creating a `size:L` issue or an epic touching ≥ 2 modules:

1. Create the SDD file at `docs/specs/{slug}.md` (status: Draft).
2. Commit it to the feature branch before creating implementation sub-tasks.
3. Link the SDD in the epic body: `**Spec**: [docs/specs/{slug}.md](../docs/specs/{slug}.md)`.
4. Set the first sub-task as: `review(spec): approve SDD for {feature}` — this is the spec gate, passed by the
   architect agent.
5. All implementation sub-tasks are `blocked_by` the spec review task.

Example dependency chain:
```
SDD Draft committed → spec-review sub-task → impl sub-tasks → test sub-tasks
```

---

## Reviewing an SDD

The architect agent checks (the owner uses the same list when reading the epic PR):

- [ ] Problem statement is clear and scoped
- [ ] Goals are measurable
- [ ] Non-goals prevent over-engineering
- [ ] BDD scenarios cover happy path + ≥1 failure path
- [ ] Data model changes are backward compatible (or migration is documented)
- [ ] API changes don't break `__init__.py` exports without a semver bump
- [ ] Edge cases are enumerated
- [ ] Open Questions are resolved (or explicitly deferred with justification)

---

## SDD and CONSTITUTION.md

An SDD may NOT propose:

- Circular imports between top-level modules
- Files named `utils.py`, `helpers.py`, `misc.py`, `common.py`
- Business logic inside view handlers
- New ORM integrations by modifying `core/`

If a design requires one of these, it must be redesigned before approval.
