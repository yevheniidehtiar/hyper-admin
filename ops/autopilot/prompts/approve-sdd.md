## Job: review and approve the SDD of an epic

Arguments: `epic` (the epic directory name), `branch` (`epic/<slug>`, checked out).

You act as the software architect. If `.claude/agents/software-architect.md` exists, read it
and follow it; this prompt is the short form.

1. Read `.meta/epics/<epic>/epic.md`, the `review(spec)` story of the epic and the SDD they
   link under `docs/specs/`. Read `.claude/rules/sdd-conventions.md` and `CONSTITUTION.md`.
2. Run the reviewer checklist of `sdd-conventions.md` against the SDD.
3. Resolve every Open Question yourself with "When you are unsure" above, and write each
   decision with its reason into the SDD's Decision Log. Fix gaps the checklist finds
   (missing scenarios, unclear module boundaries, missing test plan) directly in the SDD.
4. Escalate instead of approving only when the design needs one of: a breaking change of the
   public API, a new runtime dependency or a raised dependency floor, a data-model migration.
   Then leave the status as it is, add `needs-human` to the spec issue and post one comment
   there with the exact question, and return the verdict `escalated`.
5. Otherwise set `| Status | Approved (architect) |` in the SDD header, commit on the epic
   branch (`docs(spec): approve <name> SDD`), push with a plain `git push origin HEAD`
   (no force), and comment on the spec issue with a summary of the decisions you took.
   Do not edit the story's `status:`; the autopilot records the approval.

Return the structured verdict: `approved` or `escalated`, with the question when escalated.
