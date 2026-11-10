## Job: write the daily owner digest

The `Input` section below is JSON: `notes` are the lines the autopilot queued since the last
digest, `janitor` holds the clean-up candidates and whether clean-up is approved. Do not
change anything in this job; you may read with `gh pr list`, `gh pr view` and `gh issue list`
to check what is still true.

Write the digest as your final message, in plain Markdown, and nothing else (no greeting, no
`Applying rules` line, no closing remark). It is posted as it is. Keep it short; leave out a
section that has nothing in it. If nothing needs the owner, say so in one line.

Sections, in this order:

1. **Needs your click**: pull requests waiting for the owner's approval (epic pull requests
   marked ready, fixes to `develop`, green Dependabot pull requests), each with number, title
   and one line on what it is.
2. **Needs your answer**: open `needs-human` items with the exact question that was asked.
3. **Done since the last digest**: story pull requests merged, epics opened or handed over.
4. **Trouble**: red runs on `develop`, jobs that failed or were denied a tool call, spent
   retry budgets, a usage-limit cooldown.
5. **Clean-up**: how many worktrees and branches the janitor would remove and how to approve
   it (`ops/autopilot/autopilot.sh janitor approve`), only while it is not approved.
