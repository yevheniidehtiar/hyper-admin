# Hook-First Planning Instructions

## Objective

Use the `UserPromptSubmit` hook as the first source of truth for coding
rules and planning guidance.

These instructions apply to both `AGENTS.md` and `CLAUDE.md`.

## Hook-First Rule

Before answering any request that may lead to planning, code generation,
refactoring, architecture, or tests, you MUST first use the hook-injected
context tagged `[Coding Rules from Rippletide]` when it is present.

This requirement applies especially to plan mode requests such as:

- `/plan ...`
- requests that ask for a step-by-step implementation plan
- requests that ask what should be built before writing code

## Required Behavior Before Plan Mode

When the user enters a plan-style request, the assistant must treat the
hook result as input that is processed before producing the plan.

If hook rules are present:

1. Begin the response by explicitly naming the rules being applied.
2. Make the plan consistent with those rules.
3. Keep the rules visible in the response so the user can see what drove
   the plan.

Use a direct format such as:

`Applying rules: Rule A, Rule B, Rule C`

If the hook returns no rules, say so explicitly before continuing:

`Applying rules: none returned by hook`

## Required Behavior Before Code Generation

Before generating code, examples, patches, refactors, or tests:

1. Read the hook-injected rules first.
2. State which rules are being applied.
3. Ensure the implementation follows those rules.
4. If relevant, explain which rule changed the implementation or plan.

## Query Source

The hook query should use the user's current request text, not a fixed
prompt. For example, if the user submits:

`/plan write a hello world`

then the hook query should contain that exact text as the request being
evaluated.

## Enforcement

Do not produce planning or code output silently.

Always make the active rules explicit first when responding to plan mode
or code-related requests.

---

# Software Architect Agent

## Role

The Software Architect agent reviews structural changes against `CONSTITUTION.md` and the
project roadmap (`ROADMAP.md`). Its purpose is to catch structural debt before it lands in
`master`, not to enforce style (that is the linter's job).

## When to Activate

Invoke this agent's review checklist on any PR that:
- Adds a new module or package under `src/hyperadmin/`
- Moves, renames, or deletes existing modules
- Changes `__init__.py` exports (public API surface)
- Introduces a new external dependency

For routine feature work within an existing module, a full architect review is not required.

## Review Checklist

For each structural PR, evaluate and report pass/fail per section:

**Module boundaries**
- [ ] New module has a single, named responsibility that maps to a domain concept
- [ ] No file is named `utils.py`, `helpers.py`, `misc.py`, or `common.py`
- [ ] Nesting does not exceed two levels unless explicitly justified

**Dependency direction**
- [ ] `core/` does not import from `views/` or `adapters/`
- [ ] `adapters/` does not import from `views/`
- [ ] No circular imports between top-level modules (`python -c "import hyperadmin"` should succeed)

**Public interface**
- [ ] New public symbols are re-exported via `__init__.py`
- [ ] Breaking changes to `__init__.py` are flagged for semver consideration
- [ ] New public interface has at least one integration test

**Roadmap alignment**
- [ ] Change does not pre-emptively implement Phase 3 domains (`auth/`, `actions/`, `uploads/`)
  outside their planned phase
- [ ] Change does not create structural patterns that conflict with planned Phase 3 work
  (e.g. hardcoding auth assumptions in `core/`)

**Growth guardrails**
- [ ] No modified module exceeds ~300 LOC without justification in the PR description
- [ ] New adapter follows the `BaseAdapter` contract without modifying `core/`

## Output Format

```
## Architect Review

**Module boundaries**: PASS / FAIL — <reason if fail>
**Dependency direction**: PASS / FAIL — <reason if fail>
**Public interface**: PASS / FAIL — <reason if fail>
**Roadmap alignment**: PASS / FAIL — <reason if fail>
**Growth guardrails**: PASS / FAIL — <reason if fail>

**Overall**: PASS / NEEDS CHANGES
<one sentence summary if NEEDS CHANGES>
```
