## Job: implement one story

Arguments: `story` (the story id), `issue` (its GitHub issue, may be absent), `branch` (your
working branch, already checked out), `base` (the epic branch it was cut from, as
`origin/epic/<slug>`), `epic_of_story` (the epic directory name).

1. Find the story file: the file under `.meta/epics/<epic_of_story>/stories/` whose
   frontmatter `id` is the story id. Read it, the epic's `epic.md`, and the SDD it links.
2. Follow `.claude/skills/implement-feature/SKILL.md` for the planning, test-first
   implementation and quality gates, with these differences, which win over the skill text:
   - The base branch is the epic branch, not `develop`. The epic is already locked by its
     branch; do not look for a lock pull request.
   - Do not create a worktree or a branch: you are on `branch` already. If the branch already
     has commits from an earlier attempt, continue from them.
   - Where the skill says to post a questionnaire, halt or wait for a person, apply
     "When you are unsure" above instead.
   - Do not register a monitor or a cron job: the autopilot watches the pull request.
3. Touch only the files the story lists under `## Files to Change` (or `## Files`), plus
   their tests. If you need a hotspot file the story does not list, keep the change to its own
   small hunk and say so under `## Assumptions`.
4. Open the pull request against the epic branch (the `base` argument without `origin/`):
   `gh pr create --base epic/<slug> --title "<story title>" --body ...`. The body must contain
   a line `Story: <story id>` on its own, a summary, how it was tested, manual test scenarios
   for user-facing changes, and `## Assumptions` when you made any. Do not open it as a draft.
5. Do not merge it and do not wait for CI: the autopilot reviews, repairs and merges it.
