---
type: story
id: 01iQcyfIvwbm
title: "RFC: LLM-assisted admin setup — natural language to config via small local models"
status: todo
priority: medium
assignee: null
labels:
  - rfc
  - dx
  - ai
estimate: null
epic_ref:
  id: 5RQIGVbDMSTJ
github:
  issue_number: 277
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:6444896ed76e224d6ef3d70db4032f3ae6a74abc2e9c0dac85d4b358d816d40d
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T09:10:36Z
updated_at: 2026-03-27T09:10:36Z
---

## Summary

Integrate small local LLM models (1.5B-3B params, runs on CPU) to help users set up and customize their HyperAdmin panel via natural language — no manual config editing required. "Make the product admin show name, price, and category" → generates valid `AdminOptions` config.

Parent: #270

## Motivation

- HyperAdmin has a rich config surface (`list_display`, `search_fields`, `list_filter`, `form_columns`, `dependent_fields`, permissions...) — but users must learn it all from docs
- Non-technical users (product managers, ops teams) shouldn't need to edit Python to customize their admin
- The task is **constrained slot-filling** against a known schema, not general code generation — perfect for small models
- No admin framework offers AI-assisted configuration

## Architecture

```
User Input (natural language)
        │
        ▼
┌─────────────────────────┐
│  Schema Introspector    │  ← reads SQLModel fields, types, relationships
├─────────────────────────┤
│  Prompt Builder         │  ← system prompt with config vocabulary,
│                         │    available field names, JSON schema,
│                         │    few-shot examples
├─────────────────────────┤
│  Small LLM              │  ← Qwen 2.5-Coder 1.5B via Ollama
│  (constrained decoding) │    Output: JSON matching config schema
├─────────────────────────┤
│  Pydantic Validator     │  ← validate field names exist on model
│                         │    retry with error feedback (up to 2x)
├─────────────────────────┤
│  Code Renderer          │  ← deterministic Jinja2 template → Python
├─────────────────────────┤
│  Preview / Diff         │  ← colored diff, user confirms y/n
├─────────────────────────┤
│  Apply                  │  ← write admin.py (CLI) or update config
└─────────────────────────┘
```

**Critical safety boundary**: The LLM produces **structured data (JSON)**, never executable Python. A deterministic template converts validated data to Python source. No `eval()`, no `exec()`.

## Model Options

### Recommended: Qwen 2.5-Coder 1.5B-Instruct

| Model | Size (Q4) | Speed (CPU) | License | Why |
|-------|-----------|-------------|---------|-----|
| **Qwen 2.5-Coder 1.5B** | ~1.0 GB | 2-5s | Apache 2.0 | Best code gen at this size, excellent JSON output |
| Qwen 2.5-Coder 3B | ~1.8 GB | 3-7s | Research | Marginally better quality |
| Llama 3.2 1B/3B | 0.7/1.8 GB | 2-5s | Meta | Weaker at structured JSON |
| Gemma 3 1B/4B | 0.7/2.5 GB | 2-6s | Google | Less code-specialized |
| Phi-3.5 Mini 3.8B | ~2.2 GB | 4-8s | MIT | Larger than needed |

**Minimum viable**: 1.5B parameters (Q4), ~1 GB RAM. The task is slot-filling against known field names — far simpler than general code generation.

### Runtime Options

| Runtime | Use Case |
|---------|----------|
| **Ollama** (recommended) | Easiest: `ollama pull qwen2.5-coder:1.5b`, HTTP API, built-in JSON mode |
| llama-cpp-python | Direct Python integration, GBNF grammar for guaranteed JSON |
| ONNX Runtime GenAI | Best CPU latency, cross-platform, higher setup complexity |

## Use Cases & Prompt Patterns

### A. List View: "Show name, price, and category in the product list"
```python
# Generated:
list_display = ["name", "price", "category"]
```

### B. Search: "Let me search products by name and description"
```python
search_fields = ["name", "description"]
```

### C. Filters: "Add filters for status and date range on orders"
```python
list_filter = ["status", "date_range"]
```

### D. Form: "Hide internal_notes and created_at from the create form"
```python
form_create_exclude = ["internal_notes", "created_at"]
```

### E. Permissions: "Make the audit log read-only"
```python
AdminOptions(can_create=False, can_edit=False, can_delete=False)
```

### F. Cascading: "When I pick a country, reload the city dropdown"
```python
dependent_fields = {"city_id": "country_id"}
```

## Output Schema (Pydantic-validated)

```python
class GeneratedAdminConfig(BaseModel):
    list_display: list[str] = []
    search_fields: list[str] = []
    list_filter: list[str] = []
    form_columns: list[str] | None = None
    form_create_exclude: list[str] | None = None
    can_create: bool = True
    can_edit: bool = True
    can_delete: bool = True
    dependent_fields: dict[str, str] = {}
    icon: str = ""
    name_plural: str | None = None
```

Constrained decoding (Ollama JSON mode / GBNF grammar) forces valid JSON. Pydantic validates. Field names checked against actual model schema. Invalid → retry with error feedback (up to 2x).

## Interaction Modes

### Mode A: CLI Assistant (Recommended First)

```bash
hyperadmin init --ai
```

- Introspects registered SQLModel models
- Feeds schema to LLM, asks "How would you like to configure [Model]?"
- Generates `admin.py` files, shows diff, user confirms
- **No runtime LLM dependency** — config is generated once and committed

### Mode B: Dashboard Chat Widget (Phase 2)

- HTMX-powered chat panel in admin sidebar
- User types natural language → LLM generates config diffs → preview → apply
- Requires Ollama sidecar or remote API
- Non-technical users can customize without editing Python

### Mode C: Natural Language Config File (Experimental)

- `hyperadmin.natural.yaml` with prose/comments → build step converts to Python
- Version-controllable but fragile; secondary format

## Safety & Validation

| Layer | Mechanism |
|-------|-----------|
| **Schema constraint** | LLM outputs JSON matching `GeneratedAdminConfig` schema (constrained decoding) |
| **Field validation** | Check every field name exists on the target SQLModel (set membership) |
| **No code execution** | LLM produces data, deterministic template renders Python. No `eval()`/`exec()` |
| **Preview/diff** | CLI: colored diff + y/n. Dashboard: side-by-side preview panel |
| **Rollback** | CLI: git auto-commit before changes. Dashboard: config version history + undo |
| **Retry with feedback** | Invalid output → feed Pydantic errors back to LLM → retry (max 2x) |

## Existing Precedents

| Tool | Pattern | Takeaway |
|------|---------|----------|
| **Vercel v0** | Composite model + RAG + AutoFix validator | Our Pydantic validation = deterministic "autofixer" |
| **PydanticAI** | Structured output + validation retry + Ollama support | Ready-made orchestration layer for this exact pipeline |
| **Django AI** | Expose backend methods as LLM tools | HyperAdmin could expose `set_list_display()` etc. as tool calls |
| **GitHub Copilot** | Generate code, show as diff, user accepts/rejects | Same UX pattern for config preview |

## Resource Requirements (End User)

- Minimum: **2 GB free RAM** (1.5B Q4 model)
- Ollama install: ~200 MB + model download
- First model pull: ~1 GB (one-time)
- Inference: 2-5s on modern CPU, <1s with GPU
- **Optional** — falls back to remote API (OpenAI/Anthropic) if Ollama not installed

## Implementation Plan

### Phase 1: CLI (`hyperadmin init --ai`)
- Schema introspector for SQLModel models
- Prompt builder with config vocabulary + few-shot examples
- Ollama integration with Qwen 2.5-Coder 1.5B
- Pydantic validation + field checking
- Deterministic code renderer (Jinja2 template)
- Diff preview + confirmation

### Phase 2: Dashboard Chat Widget
- HTMX chat panel component
- Server endpoint proxying to Ollama
- Config diff preview UI
- Apply/rollback mechanism

### Phase 3: Advanced
- Multi-model config (configure multiple models in one conversation)
- Learn from existing `admin.py` patterns (RAG on user's codebase)
- Custom command vocabulary per deployment

## Open Questions

- [ ] **PydanticAI as orchestration layer?** Handles structured output, validation retries, provider abstraction (Ollama/OpenAI/Anthropic) through single interface
- [ ] **Model bundling**: Should `hyperadmin[ai]` extras auto-pull the Ollama model on first use?
- [ ] **Privacy**: Document that Ollama runs 100% locally — no data leaves the machine
- [ ] **Remote fallback UX**: If Ollama not installed, prompt user to install or use remote API?
- [ ] **Fine-tuning**: Worth fine-tuning on HyperAdmin config patterns for even smaller models?

## References

- [Qwen 2.5-Coder](https://ollama.com/library/qwen2.5-coder) — recommended model
- [PydanticAI Structured Output](https://ai.pydantic.dev/output/) — orchestration layer
- [Vercel v0 Architecture](https://vercel.com/blog/v0-composite-model-family) — comparable system
- [Constrained Decoding Guide](https://www.aidancooper.co.uk/constrained-decoding/) — JSON mode internals
- [Django AI](https://www.vintasoftware.com/blog/django-ai) — comparable Django project

---
https://claude.ai/code/session_01XktRz2PFThVGgPMoUmaEjc
