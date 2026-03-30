# Agent 6: Release Agent

| Property | Value |
|---|---|
| **Tier** | Production Model (Decision Logic) |
| **Trigger** | All tasks in milestone pass QA |
| **Purpose** | Prepare release candidate, generate changelog, publish package |
| **Est. Cost** | 10k - 30k tokens per release cycle |

## Release Pipeline

```
All milestone tasks QA-green
  │
  ▼
1. PREPARE RELEASE CANDIDATE
   └── Claude Sonnet reviews:
       - All issues in milestone closed?
       - Any "blocked" issues remaining?
       - Backward compat report clean?
       - Test coverage meets threshold?
       └── Output: RC readiness report
  │
  ▼
2. HUMAN APPROVAL GATE
   └── Human reviews RC report
   └── Approves or requests changes
  │
  ▼
3. VERSION BUMP
   └── commitizen (cz bump)
   └── Conventional commits → determines semver
   └── Generates CHANGELOG.md
  │
  ▼
4. GITHUB RELEASE
   └── gh release create v0.1.0 --generate-notes
   └── Attaches changelog, migration guide if breaking
  │
  ▼
5. PACKAGE PUBLISH
   └── PyPI: python -m build && twine upload dist/*
   └── Triggered by GitHub Actions on release tag
  │
  ▼
6. DOCUMENTATION
   └── Docs site rebuild (mkdocs)
   └── API reference regenerated
   └── Version selector updated
  │
  ▼
7. POST-RELEASE
   └── Update project memory
   └── Close milestone
   └── Notify community (GitHub Discussion)
   └── Update roadmap for next milestone
```

## Changelog Generation

Using commitizen with conventional commits:

```toml
[tool.commitizen]
name = "cz_conventional_commits"
version = "0.1.0"
tag_format = "v$version"
changelog_file = "CHANGELOG.md"
update_changelog_on_bump = true
```

Commit format determines version bump:

- `feat:` → minor version bump
- `fix:` → patch version bump
- `feat!:` or `BREAKING CHANGE:` → major version bump

## Deprecation Management

```json
{
  "deprecations": [
    {
      "api": "HttpClient.fetch()",
      "deprecated_in": "v0.2.0",
      "removal_target": "v1.0.0",
      "replacement": "HttpClient.request()",
      "migration_guide": "docs/migration/v0.2-fetch-to-request.md"
    }
  ],
  "support_matrix": {
    "v0.1.x": { "status": "active", "python": ">=3.10" },
    "v0.2.x": { "status": "active", "python": ">=3.11" }
  }
}
```
