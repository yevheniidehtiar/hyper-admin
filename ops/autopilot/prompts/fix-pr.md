## Job: repair one pull request

Arguments: `pr` (the number), `branch` (its head branch, checked out), `reason` (why the
autopilot sent you: failed checks, cancelled checks, a conflict, or review findings),
`epic_pr` (`true` when this is the draft pull request of an epic branch).

If the pull request carried `ai-approved`, whatever you push is reviewed again before the
merge: the approval counts only for the commit the reviewer saw.

1. Read the state: `gh pr view <pr> --json title,body,baseRefName,mergeable,statusCheckRollup,labels,comments`.
2. Failed checks: read the logs with `gh run view <run-id> --log-failed` (the run id is in the
   check's details URL), find the cause and fix it in the code or the tests. Do not weaken or
   skip a test to get green, and do not edit CI configuration.
3. Review findings (`ai-changes-requested`): the latest comment starting with `AI review:`
   lists the blocking findings. Fix each one. If you disagree with a finding, say why in your
   reply instead of ignoring it.
4. Conflict, or the branch is behind its base: `git fetch origin`, then
   `git rebase origin/<base>` and resolve the conflicts. For `uv.lock` never merge by hand:
   take the base's lock, finish the rebase, run `uv run uv lock` (plain `uv lock` is outside the allowlist), commit the result.
   Exception: when `epic_pr` is `true`, do not rebase and do not force-push. The epic branch
   is shared with open story pull requests; add a normal fix commit instead.
5. Run the checks from the ground rules, commit, and push (`--force-with-lease` after a
   rebase, a plain push otherwise).
6. Post one comment on the pull request saying what you changed for which finding or failure.

Do one round only: when your push is out, end the job. The autopilot looks at the result on
its next tick and has a budget of three rounds per pull request.
