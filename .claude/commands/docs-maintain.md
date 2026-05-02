---
description: Review and maintain the documentation site
---

You are the Documentation Maintenance Agent for HyperAdmin. Audit the MkDocs documentation site for structure, quality, and correctness.

## Step 1 — Read Current State

1. Read `mkdocs.yml` to understand the nav structure
2. List all `.md` files in `docs/` (excluding `agentic-workflow/` and `design/` which are internal)

## Step 2 — Structural Checks

1. **Orphan pages**: Find `.md` files in `docs/` that are NOT listed in `mkdocs.yml` nav and NOT in excluded directories (`agentic-workflow/`, `design/`). Report them.
2. **Broken internal links**: For each `docs/*.md` file in the nav, find markdown links `[text](path.md)` and verify the target file exists relative to the linking file.
3. **Stub pages**: Flag any nav-listed page with fewer than 10 lines of content.
4. **Missing navigation links**: Check if sequential pages (getting-started, tutorial, examples) have "Next:" links at the bottom.

## Step 3 — Content Quality

For each page listed in the nav, check:

1. **Title**: Every page must start with a `# Title` heading.
2. **Code blocks**: Python code blocks should use ` ```python ` syntax highlighting.
3. **Internal-only content**: Flag any content that references internal file paths (`src/hyperadmin/...`), status markers (`DONE`, `Partial`, `Not started`), or `**Status:**`/`**Files:**` lines. These belong in internal docs, not user-facing pages.
4. **Stale content**: Flag sections describing features as "planned" or "future". Cross-reference with `src/hyperadmin/` to check if the feature has since been implemented.
5. **API reference**: For each `:::` directive in `docs/api/`, verify the referenced module or class exists in `src/hyperadmin/`.

## Step 4 — Build Verification

Run `just docs-build` and report any warnings or errors.

## Step 5 — Report

Output a structured report:

```
### Documentation Health Report

**Pages audited:** N
**Issues found:** N

#### Critical (must fix)
- [ ] Issue description — file path

#### Warnings (should fix)
- [ ] Issue description — file path

#### Suggestions (nice to have)
- [ ] Issue description — file path
```

If the build succeeded with no issues, say so clearly.
