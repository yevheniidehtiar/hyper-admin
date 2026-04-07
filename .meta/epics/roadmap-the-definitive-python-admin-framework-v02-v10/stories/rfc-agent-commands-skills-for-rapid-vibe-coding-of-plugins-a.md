---
type: story
id: GxY-a8jTOBVT
title: "RFC: Agent commands & skills for rapid vibe coding of plugins and custom solutions"
status: todo
priority: medium
assignee: null
labels:
  - rfc
  - dx
  - agentic-workflow
estimate: null
epic_ref:
  id: 5RQIGVbDMSTJ
github:
  issue_number: 275
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c51f5e044522c050a7a7d4c2c72234e3f814a8e3654f3d8a49db87594da54138
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T09:06:13Z
updated_at: 2026-03-27T09:06:13Z
---

## Summary

Design a catalog of Claude Code slash commands and agent skills that enable rapid, cost-effective "vibe coding" of HyperAdmin plugins, widgets, adapters, and custom solutions — from natural language to working code.

Parent: #270

## Motivation

HyperAdmin's plugin system (Phase 6) will only succeed if creating plugins is frictionless. Developers should be able to say "create a plugin that adds a markdown editor widget" and get a working, tested, CONSTITUTION-compliant plugin. The commands and skills defined here make that possible by combining template-heavy scaffolding (cheap) with guided implementation (cost-effective).

## Command Catalog (`.claude/commands/`)

### Tier 1 — High Value (template-heavy, low token cost)

| Command | Purpose | Cost Profile |
|---------|---------|-------------|
| `/scaffold-plugin <name>` | Full plugin skeleton: `pyproject.toml` with entry points, `src/<name>/`, `__init__.py` with `on_register` hook, tests, README | ~90% boilerplate, ~10% LLM fill |
| `/add-widget <WidgetName>` | Custom widget: `HtmxWidget` subclass, Jinja2 template under `templates/widgets/`, test file | ~85% boilerplate (~10 LOC class + ~21 LOC template) |
| `/add-model <ModelName>` | SQLModel model, `site.register()`, `AdminOptions`, scaffold tests | ~80% boilerplate |
| `/add-adapter <ORMName>` | New adapter under `adapters/`: subclass `BaseAdapter` (7 abstract methods), register in `AdapterRegistry` | ~70% boilerplate, reference impl is ~200 LOC |

### Tier 2 — Medium Value (more reasoning needed)

| Command | Purpose | Cost Profile |
|---------|---------|-------------|
| `/add-action <ActionName>` | Bulk action class, registration hook, template partial, test | Depends on Phase 3 `actions/` design |
| `/add-dashboard-widget <name>` | Dashboard widget scaffold | Depends on Phase 5 design |
| `/migrate-view <DjangoAdminClass>` | Parse Django `ModelAdmin` → generate HyperAdmin equivalent | ~50% template, ~50% reasoning |

### Command Design Principles

Each command should:
1. Embed relevant CONSTITUTION.md rules inline (avoids Read tool call)
2. Contain literal template strings with `{{NAME}}` placeholders (LLM only fills variable parts)
3. End with `poe lint` validation
4. Restrict `allowed-tools` to `Write`, `Edit`, `Bash(poe lint)`

## Agent Skill Catalog (`.claude/skills/`)

| Skill | Model | Purpose |
|-------|-------|---------|
| `implement-plugin` | Sonnet | Full plugin from natural language. Phases: parse intent → self-evaluate vs CONSTITUTION → scaffold → implement → test → lint → PR |
| `review-plugin` | Haiku | Review plugin against CONSTITUTION.md: adapter contract, dependency direction, naming conventions. Checklist evaluation. |
| `migrate-from-django` | Sonnet | Analyze Django `admin.py`, map `ModelAdmin` fields to `AdminOptions`, generate complete registration code |
| `optimize-queries` | Haiku | Analyze adapter usage for N+1 queries, missing `selectinload()`, pagination issues |

### Skill Design Pattern (from `implement-feature`)

The self-evaluation gate is critical — every skill should validate against CONSTITUTION.md before generating code:

```
Phase A: Parse intent & plan
Phase B: Self-evaluate against CONSTITUTION.md
  - Widget belongs in views/ layer? ✓
  - No core/ imports from views/? ✓
  - Template under templates/widgets/? ✓
Phase C: Scaffold (cheap, Haiku-eligible)
Phase D: Implement (Sonnet)
Phase E: Validate (poe lint + poe test) + PR
```

## Cost Optimization Strategy

### Model Tiers

| Operation | Model | Rationale |
|-----------|-------|-----------|
| Scaffolding (`/scaffold-plugin`, `/add-widget`, `/add-model`) | **Haiku** | 90%+ boilerplate |
| Plugin implementation (`implement-plugin`) | **Sonnet** | Needs business logic reasoning |
| Architecture review (`review-plugin`) | **Haiku** | Checklist evaluation, no creative output |
| Migration (`migrate-from-django`) | **Sonnet** | Cross-domain model mapping |
| Complex architecture | **Opus** | Only for `plan-roadmap` or manual escalation |

### Token Reduction Techniques

1. **Pre-baked file reads** — Embed key patterns (BaseAdapter ABC, HtmxWidget class, TextInput widget) directly in command prompts instead of runtime file reads. Saves ~400 tokens per invocation.

2. **Template strings over generation** — Commands contain literal templates with placeholders, not instructions like "generate a class that..."

3. **Allowed-tools restriction** — Prevent unnecessary tool calls via SKILL.md `allowed-tools` frontmatter

4. **Exit early on validation** — Self-evaluation gate prevents wasting tokens on code that violates rules

## Vibe Coding Workflow

```
User: "create a plugin that adds a markdown editor widget"
                    │
                    ▼
    /implement-plugin "markdown editor widget"
                    │
    ┌───────────────┼───────────────┐
    │  Phase A: Parse intent        │
    │  - Widget type: HtmxWidget    │
    │  - Template: markdown preview │
    │  - JS dep: marked.js          │
    │  - No adapter/core changes    │
    ├───────────────┼───────────────┤
    │  Phase B: CONSTITUTION check  │
    │  - views/ layer: PASS         │
    │  - No core→views import: PASS │
    │  - templates/widgets/: PASS   │
    ├───────────────┼───────────────┤
    │  Phase C: Scaffold            │
    │  (internally /scaffold-plugin)│
    ├───────────────┼───────────────┤
    │  Phase D: Implement + Test    │
    │  - MarkdownWidget class       │
    │  - markdown_editor.html       │
    │  - Unit + E2E tests           │
    ├───────────────┼───────────────┤
    │  Phase E: poe lint + poe test │
    │  - PR via CLAUDE_GH_TOKEN     │
    └───────────────┴───────────────┘
```

### Command Chaining
1. `/scaffold-plugin <name>` — skeleton (Haiku, cheap)
2. `/implement-plugin <issue>` — logic (Sonnet)
3. Code reviewer agent auto-triggers on PR (Haiku)
4. Delivery manager monitors CI (Haiku)

## Context Injection Strategy

| Context | Method | Why |
|---------|--------|-----|
| CONSTITUTION.md rules | Embed relevant sections in prompt | Avoids Read call (~200 tokens saved) |
| `BaseAdapter` ABC (7 methods) | Embed signatures in `/add-adapter` | Stable contract, 110 LOC |
| `HtmxWidget` + `TextInput` | Embed in `/add-widget` | 20 LOC base + 3 LOC example |
| `AdminOptions` + registration | Embed in `/add-model` | 36 LOC + 5 LOC example |
| E2E `data-testid` conventions | Embed table from CLAUDE.md | Stable reference for test generation |
| Test fixtures | Read at runtime | Change more often, embedding risks staleness |

### Hook Additions to Consider

- `PostToolUse` on `Write` to `adapters/*.py` — verify adapter implements all BaseAdapter abstract methods
- `PostToolUse` on `Write` to `tests/e2e/*.py` — grep for forbidden `.ha-*` selectors
- `PostToolUse` on plugin Write/Edit — auto-restart dev server for immediate visual feedback

## Deliverables

- [ ] `/scaffold-plugin` command
- [ ] `/add-widget` command
- [ ] `/add-model` command
- [ ] `/add-adapter` command
- [ ] `implement-plugin` skill (SKILL.md, 200+ LOC)
- [ ] `review-plugin` skill
- [ ] `migrate-from-django` skill
- [ ] Hook additions to `settings.json`

## Open Questions

- [ ] Should `/migrate-view` accept Django `admin.py` as file path or pasted code?
- [ ] Plugin hot-reload: extend existing `redeploy-example.sh` hook or separate mechanism?
- [ ] Should skills support `--dry-run` to preview generated code without writing?
- [ ] How to handle plugin dependencies (e.g., `marked.js` for markdown widget)?

---
https://claude.ai/code/session_01XktRz2PFThVGgPMoUmaEjc
