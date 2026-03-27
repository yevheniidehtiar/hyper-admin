# Sync Agentic Workflow Improvements Back to Template

> **Source repo**: `yevheniidehtiar/hyper-admin` (downstream consumer)
> **Target repo**: `Damdy-OSS/oss-scaffold-agentic-workflow` (upstream copier template)
> **Baseline commit**: `a3b4854` — the commit that applied the template to hyper-admin
> **Diff window**: `a3b4854..HEAD` (12 commits touching agentic workflow files)

---

## Instructions for the Template Repo Agent

When you open a session on `Damdy-OSS/oss-scaffold-agentic-workflow`, read this plan and:

1. Fetch each source file from `yevheniidehtiar/hyper-admin` (main branch) using the GitHub MCP tools
2. Apply the categorization below — copy A-items verbatim, templatize B-items, apply D-fixes
3. Skip C-items entirely (they are project-specific)

---

## Category D — Bug Fixes to Existing Template Files

These fix bugs that affect **every** project generated from the current template. Apply them first.

| # | File | Fix |
|---|------|-----|
| D1 | `template/.github/workflows/ci.yml` | Add `permissions: contents: read` at workflow level. Add `env: UV_PYTHON: ${{ matrix.python-version }}` to test job. Fix coverage path to `--cov=src/{{ python_package_name }}` |
| D2 | `template/.github/workflows/code-review.yml` | Add `if: false # TODO: Enable after setting up ANTHROPIC_API_KEY` on the Claude action step. Add `id-token: write` to permissions |
| D3 | `template/.github/workflows/community.yml` | Add explicit `permissions:` block (`contents: read`, `issues: write`, `pull-requests: write`, `id-token: write`). Add `if: false` guard on Claude action step |
| D4 | `template/.github/workflows/gemini-review.yml` | Add `if: false # TODO: Enable after setting up GEMINI_API_KEY` on the Gemini review step |
| D5 | `template/.github/workflows/qa.yml` | Add explicit `permissions:` block (`contents: read`, `pull-requests: write`, `id-token: write`). Add `if: false` guard on AI step |
| D6 | `template/.github/workflows/release.yml` | Add `permissions: contents: write, id-token: write`. Add `if: false` guard on Claude step |
| D7 | `template/.github/workflows/scheduled.yml` | Add `permissions: contents: read, issues: write, id-token: write`. Add `if: false` guard on Claude step |

**Pattern**: Every workflow with a Claude/Gemini action step needs:
- `if: false # TODO: Enable after setting up <API_KEY>`
- Explicit least-privilege `permissions:` block

### Reference diffs

Fetch the fixed versions from hyper-admin:
- `yevheniidehtiar/hyper-admin:.github/workflows/ci.yml`
- `yevheniidehtiar/hyper-admin:.github/workflows/code-review.yml`
- `yevheniidehtiar/hyper-admin:.github/workflows/community.yml`
- `yevheniidehtiar/hyper-admin:.github/workflows/gemini-review.yml`
- `yevheniidehtiar/hyper-admin:.github/workflows/qa.yml`
- `yevheniidehtiar/hyper-admin:.github/workflows/release.yml`
- `yevheniidehtiar/hyper-admin:.github/workflows/scheduled.yml`

---

## Category A — Generic Additions (copy verbatim)

No copier variables needed. Copy these files as-is from hyper-admin into the template.

| # | Source path in hyper-admin | Target path in template | Description |
|---|--------------------------|------------------------|-------------|
| A1 | `scripts/triage_audit.py` | `template/scripts/triage_audit.py` | 1129-line generic OSS triage script (AI-slop, ego-PR, duplicates, lifecycle, TTL) |
| A2 | `.claude/agents/oss-triage-auditor.md` | `template/.claude/agents/oss-triage-auditor.md` | Agent definition — delegates to script, security guardrails |
| A3 | `.claude/commands/oss-triage-audit.md` | `template/.claude/commands/oss-triage-audit.md` | Command stub: `uv run scripts/triage_audit.py $ARGUMENTS` |
| A4 | `docs/agentic-workflow/oss-triage-auditor.md` | `template/docs/agentic-workflow/oss-triage-auditor.md` | Full spec with scoring heuristics and security model |
| A5 | `.claude/commands/plan-roadmap.md` | `template/.claude/commands/plan-roadmap.md` | Roadmap Planning Agent command (replaces old `plan.md` / `plan-command.sh`) |
| A6 | `.claude/commands/implement-feature.md` | `template/.claude/commands/implement-feature.md` | Redirect stub to the `implement-feature` skill |

Also **remove** from template (if they still exist):
- `.claude/commands/plan.md`
- `.claude/commands/plan-command.sh`

---

## Category B — Templatizable (need copier variable substitution)

Fetch each file from hyper-admin, then apply the substitutions described.

### B1. `.claude/agents/delivery-manager.md`

**Source**: `yevheniidehtiar/hyper-admin:.claude/agents/delivery-manager.md`

Substitutions:
- Replace "HyperAdmin project" → `{{ project_name }} project`
- Remove `ha-*` CSS references (lines 38-39) — replace with generic "project CSS class convention"
- Remove `data-testid` specific values — replace with "see project's `data-testid` reference in CLAUDE.md"
- Keep all structural content (5 sections, notification formats, decision framework, memory)

### B2. `.claude/skills/implement-feature/SKILL.md`

**Source**: `yevheniidehtiar/hyper-admin:.claude/skills/implement-feature/SKILL.md`

Substitutions:
- Line 9: "for HyperAdmin" → "for {{ project_name }}"
- Line 24: `src/hyperadmin/` → `src/{{ python_package_name }}/`
- Lines 47-48: Remove Phase 3 domain refs (`auth/`, `actions/`, `uploads/`) — replace with generic "phase-reserved domains (see CONSTITUTION.md)"
- Lines 57-58: Remove `selectinload()` specifics — replace with generic "ORM best practices per code-style.md"
- Lines 62-63, 229: Remove `ha-*` CSS ref — replace with "project CSS class convention"
- Lines 136-137, 186-187: Replace hardcoded `/Users/yevheniidehtiar/.claude/projects/...` with `.claude/agent-memory/implement-feature/`
- Keep all 3 phases, 5 self-eval dimensions, blocker protocol, memory system

### B3. `.claude/skills/fix-issue/SKILL.md`

**Source**: `yevheniidehtiar/hyper-admin:.claude/skills/fix-issue/SKILL.md`

Substitutions:
- Line 9: "for HyperAdmin" → "for {{ project_name }}"
- Line 24: `src/hyperadmin/` → `src/{{ python_package_name }}/`
- Line 35: Remove `ha-*` CSS ref — replace with "project CSS class convention (see testing.md)"

### B4. `.claude/agents/hyper-admin-code-reviewer.md` → `code-reviewer.md`

**Source**: `yevheniidehtiar/hyper-admin:.claude/agents/hyper-admin-code-reviewer.md`

Major changes:
- **Rename** to `code-reviewer.md`
- Agent name in frontmatter: `code-reviewer` (not `hyper-admin-code-reviewer`)
- Line 9: Replace HyperAdmin stack description with `{{ project_name }}` + generic Python stack
- Sections 1-5: Remove framework-specific items (SQLModel, HTMX, Pydantic v2, `ha-*` CSS, `data-testid` table). Replace with generic placeholders: "Verify architecture per CONSTITUTION.md", "Check model conventions per code-style.md", etc.
- Sections 6 (Git) and 8 (General Quality): Keep as-is — fully generic
- Section 7 (Deps): Keep as-is — generic Python dep management
- Memory path: `.claude/agent-memory/code-reviewer/`

### B5. `docs/agentic-workflow/onboarding.md`

**Source**: `yevheniidehtiar/hyper-admin:docs/agentic-workflow/onboarding.md`

Substitutions:
- Replace all "HyperAdmin" → `{{ project_name }}`
- Replace `src/hyperadmin/**/*.py` → `src/{{ python_package_name }}/**/*.py`
- Replace absolute memory paths → relative `.claude/agent-memory/` convention
- Remove framework-specific items (HTMX, Alpine.js, SQLModel, `ha-*`, `data-testid` specifics)
- Keep the full structure (12 sections, setup checklist)

### B6. `CLAUDE.md` additions

**Source**: `yevheniidehtiar/hyper-admin:CLAUDE.md` (lines 142-170)

Add to the template's CLAUDE.md:
- "Agentic Workflow" section listing the 8 agents (generic)
- "MCP Servers in Use" section (generic)
- "Key Files" table (generic)
- **Omit**: E2E selector convention, `data-testid` table, `ha-*` refs (project-specific)

### B7. `.claude/settings.json`

**Source**: `yevheniidehtiar/hyper-admin:.claude/settings.json`

Keep:
- PostToolUse hook for ruff auto-format on `*.py` files after Edit/Write (generic for any Python project)

Remove/comment-out:
- TaskUpdate → `scripts/redeploy-example.sh` hook (project-specific). Leave as a commented JSON example.

### B8. `justfile` changes

**Source**: `yevheniidehtiar/hyper-admin:justfile` (diff from `a3b4854`)

Add to template:
- `test-e2e` target: `uv run poe test:e2e`
- Fix `test` target: `uv run poe test:unit` (was `uv run pytest --tb=short -q`)
- Fix `test-cov` coverage path: `--cov=src/{{ python_package_name }}`

**Do NOT** add: `run-erp`, `run-simple` (project-specific example apps)

---

## Category C — Project-Specific (do NOT sync)

These stay in hyper-admin only:

| Item | Reason |
|------|--------|
| `justfile` `run-erp` / `run-simple` targets | HyperAdmin example apps |
| `data-testid` reference table in CLAUDE.md | HyperAdmin UI testing contract |
| `ha-*` CSS selector convention | HyperAdmin styling pattern |
| `.claude/hooks/fetch-rules.sh` (Rippletide) | Personal/company external service |
| `selectinload()`, HTMX, Alpine.js in rules | Framework-specific |
| Absolute memory paths `/Users/yevheniidehtiar/` | User-specific |

---

## Template Design Decisions (decide during implementation)

1. **Remove `scripts/lint.sh` and `scripts/release.sh`?** — hyper-admin removed them in favor of justfile/poe. Template should follow suit.
2. **Include Rippletide hook as example?** — Could add a `.claude/hooks/fetch-rules.sh.example` showing the pattern without the specific service.
3. **Memory path convention**: Standardize on relative `.claude/agent-memory/<agent-name>/` (not absolute user-home paths).

---

## Copier Variables Reference

These should already exist in the template's `copier.yml`:
- `{{ project_name }}` — e.g., "HyperAdmin"
- `{{ project_slug }}` — e.g., "hyper-admin"
- `{{ python_package_name }}` — e.g., "hyperadmin"

No new copier variables are needed.

---

## Verification Checklist

After applying all changes to the template:

1. `copier copy . /tmp/test-project` — generate a test project
2. Confirm all `if: false` guards are in place in `.github/workflows/`
3. Confirm `scripts/triage_audit.py` exists and has no hardcoded project refs
4. Confirm all `.claude/` files use `{{ project_name }}` / `{{ python_package_name }}` — no "HyperAdmin" or "hyperadmin" literals
5. Confirm no absolute paths like `/Users/...`
6. Confirm `uv sync --all-extras && poe lint` passes in the generated project
7. Confirm `/implement-feature`, `/fix-issue`, `/plan-roadmap`, `/oss-triage-audit` commands are present

---

## Summary

| Category | Count | Description |
|----------|-------|-------------|
| D (Bug fixes) | 7 | Workflow permissions + API key guards |
| A (Generic) | 6 | Triage auditor ecosystem + plan-roadmap + implement-feature redirect |
| B (Templatizable) | 8 | Agents, skills, onboarding docs, settings, justfile |
| C (Project-specific) | 6 | Stay in hyper-admin only |
| **Total actionable** | **21** | |
