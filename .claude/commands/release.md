---
description: Cut a new release
---
1. Check `git status` is clean
2. Read CHANGELOG.md for unreleased entries
3. Run `uv run poe lint && uv run poe test`
4. Ask user to confirm version bump (patch/minor/major). A release is always the owner's call: never run this
   unattended (`AUTOPILOT=1`).
5. Run `uv run cz bump --changelog` (add `--increment PATCH|MINOR|MAJOR` to force the confirmed bump), then push
   the branch and tags
6. Summarise what was released
