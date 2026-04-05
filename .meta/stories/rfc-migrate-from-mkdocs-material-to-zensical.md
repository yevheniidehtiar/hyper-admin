---
type: story
id: a9qPw5WQnJlY
title: "RFC: Migrate from MkDocs + Material to Zensical"
status: todo
priority: medium
assignee: null
labels:
  - documentation
  - enhancement
estimate: null
epic_ref: null
github:
  issue_number: 348
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7617da8e884e7126f68ca27b34d600bb70795aec7cc8dc7861fba6eb024a7018
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-30T11:50:29Z
updated_at: 2026-03-30T11:50:29Z
---

## Summary

Evaluate and plan migration from MkDocs + mkdocs-material to [Zensical](https://zensical.org) once it reaches sufficient maturity.

## Background

MkDocs 2.0 introduces backward-incompatible changes that break all plugins, themes, and configuration:

- Plugin system removed — all 300+ community plugins will stop working
- Theming system rewritten — navigation passed as pre-rendered HTML
- Configuration format changed from YAML to TOML
- No migration path for existing projects
- Currently unlicensed — unsuitable for production use

Material for MkDocs is now in [maintenance mode](https://github.com/squidfunk/mkdocs-material/issues/8523) (security fixes only through Nov 2026).

**Zensical** is a new SSG built from scratch in Rust + Python by the same creator of mkdocs-material (@squidfunk). It is MIT licensed with no Insiders gating.

- Repository: [github.com/zensical/zensical](https://github.com/zensical/zensical)
- PyPI: [`zensical`](https://pypi.org/project/zensical/) (currently v0.0.30, Alpha)
- Reads `mkdocs.yml` natively for maximum compatibility

## Current HyperAdmin docs stack

- `mkdocs>=1.6.1,<2.0` (pinned to avoid MkDocs 2.0)
- `mkdocs-material>=9.7.5`
- `mkdocstrings[python]>=1.0.3`
- Markdown extensions: admonition, pymdownx.superfences (Mermaid), pymdownx.tabbed, pymdownx.highlight
- Features: navigation.tabs, navigation.sections, content.code.copy, search.suggest

## Migration readiness checklist

Before migrating, Zensical must support:

- [ ] Stable `mkdocstrings` integration (API reference docs depend on this)
- [ ] Built-in search (Disco engine) at feature parity with MkDocs search
- [ ] Navigation tabs, sections, and expand features
- [ ] Code copy buttons
- [ ] Dark/light mode toggle
- [ ] Mermaid diagram rendering
- [ ] Stable release (v0.1.0+)

## Immediate safeguard

MkDocs is pinned to `>=1.6.1,<2.0` in `pyproject.toml` to prevent accidental MkDocs 2.0 upgrades.

## When to revisit

- Monitor Zensical releases quarterly
- Target migration window: Q3-Q4 2026 (once Zensical reaches stable release and mkdocstrings support is confirmed)
- Track: [zensical/zensical plugin compatibility](https://zensical.org/compatibility/plugins/)

## References

- [What MkDocs 2.0 means for your documentation](https://squidfunk.github.io/mkdocs-material/blog/2026/02/18/mkdocs-2.0/)
- [The Slow Collapse of MkDocs](https://fpgmaas.com/blog/collapse-of-mkdocs/)
- [Material for MkDocs maintenance mode announcement](https://github.com/squidfunk/mkdocs-material/issues/8523)
