## Job: review one story pull request

Arguments: `pr` (the pull request number), `head_sha` (the commit under review). The worktree
is on the pull request's head commit, detached. This job has read-only tools: it cannot edit
files, commit or push, and the only thing it writes is the one comment of step 4.

1. Read the pull request: `gh pr view <pr> --json title,body,baseRefName,headRefName,headRefOid,files`
   and `gh pr diff <pr>`. Find the story from the `Story: <id>` line of the body and read it,
   with its acceptance criteria and the SDD it links. Your verdict is recorded for `head_sha`
   and the autopilot merges only that commit; if `headRefOid` differs from it, return
   `request_changes` with the single finding "head moved during the review".
2. Review as `.claude/agents/hyper-admin-code-reviewer.md` describes (read that file and apply
   its checklist yourself). Check in particular:
   every acceptance criterion is met and tested; `CONSTITUTION.md` and `.claude/rules/` hold;
   the diff stays within the story's files; no dependency, CI or ignore-file change is bundled
   in; changed lines are covered by tests; nothing breaks the public API.
3. A blocking finding is a defect, a missed acceptance criterion, a rule violation or missing
   test coverage. Style preferences and ideas for later are not blocking.
4. Post exactly one comment on the pull request with `gh pr comment <pr> --body ...`: the
   verdict in the first line (`AI review: approve` or `AI review: changes requested`), then the
   blocking findings as a numbered list with file and line, then optional non-blocking notes.
   The bot cannot approve its own pull request, so do not use `gh pr review --approve`.
5. Do not set labels: the autopilot sets `ai-approved` or `ai-changes-requested` from the
   verdict you return.

Return the structured verdict: `approve` only when there is no blocking finding, otherwise
`request_changes` with the blocking findings.
