---
description: Cut a new release
---
1. Check `git status` is clean
2. Read CHANGELOG.md for unreleased entries
3. Run `just lint && just test`
4. Ask user to confirm version bump (patch/minor/major)
5. Run `just release VERSION=x.y.z`
6. Summarise what was released
