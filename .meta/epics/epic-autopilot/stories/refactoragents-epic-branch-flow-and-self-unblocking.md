---
type: story
id: st-autopilot-03
title: "refactor(agents): epic-branch flow and self-unblocking"
status: in_progress
priority: high
assignee: null
labels:
  - size:L
  - planned
  - dx
estimate: null
epic_ref:
  id: ep-autopilot-01
created_at: 2026-11-10T00:00:00Z
updated_at: 2026-11-10T00:00:00Z
---

## Summary

Bring the agent instructions in line with the autopilot.

- **Branch as lock.** `.claude/project-config.md` drops the `.meta` lock PR and the squash auto-merge. The lock is the
  creation of `epic/<slug>`; status changes happen in the open-epic and close-epic commits; the label machine is
  `ai-approved | ai-changes-requested | needs-human | ap:in-progress | ap:in-review | ap:done`. The merge-queue labels
  and every `bun "$GITPM_CLI" push` call go.
- **Self-unblocking.** `implement-feature` and `fix-issue` take a base-branch argument, write `Story: <story-id>` and
  `## Assumptions` into the PR body, and replace the questionnaire-and-HALT steps with the decision ladder: memory,
  then story/SDD/CONSTITUTION/code, then a research subagent, then the most reversible option that satisfies the
  CONSTITUTION. Hard stops (secrets or billing, the public mirror, deleting data, a PyPI release, breaking public API,
  runtime dependency floors, data-model migrations) post `needs-human` with the exact question and move on. In-session
  CI monitoring is removed; the tick owns it.
- **Spec gate.** New `.claude/agents/software-architect.md` runs the SDD reviewer checklist, resolves Open Questions
  with the ladder, fills the Decision Log and sets `Status | Approved (architect)`. It escalates only on breaking API,
  new runtime dependencies or migrations. `sdd-conventions.md` changes "Human approves" to "Architect agent approves;
  owner can veto on the epic PR".
- **Reviewer verdict.** `hyper-admin-code-reviewer` returns a JSON verdict and sets `ai-approved` or
  `ai-changes-requested` plus a review comment.
- **Roster.** `conductor`, `delivery-manager` and `/run-autonomous-team` are deleted; `project-manager` shrinks to the
  digest template; `/autopilot-tick` runs one interactive tick for debugging; `/wt` takes an optional base branch.
- **Drift sweep.** `just` to `poe` and removal of `bun` calls in skills and commands.

## Files to Change

- `.claude/project-config.md` — branch-as-lock, status machine, label machine
- `.claude/skills/implement-feature/SKILL.md`, `.claude/skills/fix-issue/SKILL.md`
- `.claude/agents/software-architect.md` (new)
- `.claude/agents/hyper-admin-code-reviewer.md`, `.claude/agents/project-manager.md`
- `.claude/agents/conductor.md`, `.claude/agents/delivery-manager.md` — delete
- `.claude/commands/run-autonomous-team.md` — delete
- `.claude/commands/autopilot-tick.md` (new)
- `.claude/commands/{wt,lint,test,optimize,refactor,release,scaffold,bootstrap,plan-to-issues}.md`
- `.claude/rules/conflict-avoidance.md` — `.meta` edits only in open/close-epic commits; only the autopilot rebases
- `.claude/rules/sdd-conventions.md`, `.claude/rules/planning-playbook.md`, `.claude/rules/git-workflow.md`
- `CLAUDE.md` — agent roster, `poe`, Dependabot cadence
- `AGENTS.md` — architect section points at the agent file

Not touched here: `.claude/settings.json` (st-autopilot-02).

## Scenarios

```
Scenario: An ambiguous plan gate no longer halts
  Given a story with an open design question that is not on the hard-stop list
  When  implement-feature reaches its plan gate
  Then  it picks the most reversible option and continues
  And   the choice is listed under "## Assumptions" in the PR body

Scenario: A hard stop is escalated without blocking
  Given a story that needs a data-model migration
  When  implement-feature reaches that decision
  Then  it posts needs-human with the exact question
  And   it stops work on that story only

Scenario: Story PR targets the epic branch
  Given implement-feature is run with base epic/some-epic
  When  it opens the PR
  Then  the PR base is epic/some-epic
  And   the body contains "Story: <story-id>"

Scenario: Reviewer verdict is a label
  Given the code reviewer finished reviewing a bot PR
  When  it reports its verdict
  Then  the PR carries exactly one of ai-approved or ai-changes-requested and a review comment

Scenario: Architect approves a Draft SDD
  Given a Draft SDD with open questions that are not on the escalation list
  When  the software-architect agent reviews it
  Then  the Decision Log records each resolution and the status is "Approved (architect)"
```

## Acceptance Criteria

- [ ] An ambiguous plan gate no longer halts
- [ ] A hard stop is escalated without blocking
- [ ] Story PR targets the epic branch
- [ ] Reviewer verdict is a label
- [ ] Architect approves a Draft SDD
- [ ] No `bun "$GITPM_CLI"`, `--auto --squash` or merge-queue label is left in the files listed above, and `just`
      is replaced by `poe` in those files (the `just cc-*` recipes documented under `.claude/container/` stay)
- [ ] No file under `.claude/agents`, `.claude/commands`, `.claude/skills`, `.claude/rules`,
      `.claude/project-config.md`, `CLAUDE.md` or `AGENTS.md` references the deleted agents or
      `/run-autonomous-team` (`docs/agentic-workflow/**` and `scripts/setup-github.sh` are st-autopilot-04;
      `.claude/experiments/**` and historical `.meta` stories stay as they are)
- [ ] `poe lint` passes

## Blocked by

- `ciautopilot-epic-branch-lane` (st-autopilot-01) — the flow sends story PRs to `epic/**`, which has no CI before it

## Parent

- Epic: `epic-autopilot`
