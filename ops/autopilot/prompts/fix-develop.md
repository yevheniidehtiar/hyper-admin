## Job: repair a red run on develop

Arguments: `run` (the id of the failed workflow run), `branch` (`fix/develop-<run>`, cut from
`origin/develop` and checked out).

1. Read the failure: `gh run view <run> --json workflowName,headSha,event,conclusion,jobs,url`
   and `gh run view <run> --log-failed`.
2. Decide what kind of failure it is:
   - **Caused by a commit on develop**: find it (`git log origin/develop`, the run's
     `headSha`, `git bisect` with the failing test if needed). Fix it forward when the fix is
     small and clear. Otherwise revert the offending commit with `git revert`.
   - **Flaky test**: only when the same commit passed before or the failure does not reproduce
     locally in three runs. Fix the cause of the flakiness; do not add a retry or a skip.
   - **External** (a hosting service, a runner, a registry, an expired credential): do not
     change code. Open an issue with `gh issue create` that names the service, quotes the
     error and links the run, label it `needs-human`, and end the job.
3. Run the checks from the ground rules, commit, push the branch.
4. Open a pull request to `develop`: `gh pr create --base develop`. The body holds a one-line
   rationale, the link to the failed run, the failing log lines, and what you did (fix or
   revert, and of which commit). The owner approves it; do not merge it.
