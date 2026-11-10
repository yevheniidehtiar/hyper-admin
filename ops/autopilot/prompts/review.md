## Job: review one story pull request

Arguments: `pr` (the pull request number). The worktree is on the pull request's head commit,
detached. Do not change or push code in this job.

1. Read the pull request: `gh pr view <pr> --json title,body,baseRefName,headRefName,files`
   and `gh pr diff <pr>`. Find the story from the `Story: <id>` line of the body and read it,
   with its acceptance criteria and the SDD it links.
2. Review as `.claude/agents/hyper-admin-code-reviewer.md` describes (read that file and apply
   its checklist; start it as a subagent if that is available). Check in particular:
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
