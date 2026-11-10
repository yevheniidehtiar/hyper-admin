## Job: hand a finished epic to the owner

Arguments: `epic` (the epic directory name), `branch` (`epic/<slug>`, checked out), `pr` (the
draft pull request from the epic branch to `develop`).

Every story of the epic is merged into the epic branch. Your job ends with that pull request
ready for the owner's single approval.

1. Check the gate first and end the job without changes if it does not hold:
   `gh pr list --base epic/<slug> --state open` must be empty.
2. Rebase on develop: `git fetch origin`, `git rebase origin/develop`, resolve conflicts
   (for `uv.lock`: take develop's lock, finish the rebase, run `uv run uv lock`, commit). GitHub can
   only rebase-merge a branch that replays cleanly, so the branch must sit exactly on top of
   `origin/develop`.
3. Run the checks from the ground rules on the rebased branch and fix what fails.
4. Make the close-epic commit, `chore(meta): close epic <slug>`: in `.meta/epics/<epic>/`
   set `status: done` in `epic.md` and remove its `locked_by` and `branch` fields, and set
   `status: done` on every story that is merged, including the `review(spec)` story. This
   commit is the one place where this flow edits `.meta` status. Run
   `./scripts/gitpm.sh validate`.
5. Push with `git push --force-with-lease origin HEAD`.
6. Resolve the review threads that are addressed (`gh api graphql`, `resolveReviewThread`);
   unresolved threads block the merge. Leave a thread open and say so in your final message
   if it names a real problem you could not fix.
7. Update the pull request body: what the epic delivers, the list of story pull requests, the
   collected `## Assumptions` of the stories, and manual test scenarios.
8. Wait for the checks of the pushed commit (`gh pr checks <pr> --watch`); if they fail, fix
   and push once more.
9. Hand over: `gh pr ready <pr>`, request the owner's review (the code owner in
   `.github/CODEOWNERS`) with `gh pr edit <pr> --add-reviewer <login>`, then
   `gh pr merge <pr> --auto --rebase` so the approval merges it at once.

After step 9 the branch is frozen: any further push would dismiss the approval. Do not push
again.
