---
type: story
id: LHFfddBb6ZRr
title: "refactor(core): post-v0.3.0 code quality — bug fixes, CONSTITUTION compliance, dedup"
status: todo
priority: medium
assignee: null
labels:
  - refactoring
estimate: null
epic_ref: null
github:
  issue_number: 411
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:43a70a5469d58ee9ac5f49c8eb79238de9122436697cff8784035fc745cc579e
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T21:34:11Z
updated_at: 2026-03-31T21:34:11Z
---

## Context

PRs #384, #385, #386 delivered zero-config admin, pydantic-settings, and auth E2E for [milestone v0.3.0](https://github.com/yevheniidehtiar/hyper-admin/milestone/13). This issue tracks refactoring to address 2 bugs and 3 structural issues found in the merged code. No new features — only correctness fixes and code quality improvements.

---

## Change 1A — Bug: `SQLAlchemyAdapter.list()` ignores `search_fields`

**File:** `src/hyperadmin/adapters/sqlalchemy.py`

- The `search_fields` param was added to `BaseAdapter.list()` and implemented in `SQLModelAdapter`, but `SQLAlchemyAdapter.list()` hardcodes string column detection (lines 43-50)
- **Fix:** When `search_fields` is provided, use those fields; when `None`, fall back to auto-detection via a new `_detect_search_fields()` method (mirrors `SQLModelAdapter` pattern)
- **Risk:** LOW — fallback behavior unchanged

## Change 1B — Bug: `JsonApiAdapter.list_as_envelope()` doesn't forward `search_fields`

**File:** `src/hyperadmin/core/adapters.py`

- `list_as_envelope()` (line 223) lacks `search_fields` param and doesn't pass it to `self.list()` (line 246)
- **Fix:** Add `search_fields: list[str] | None = None` to signature, forward to `self.list()`
- **Risk:** LOW — additive, default is `None`

## Change 2 — CONSTITUTION violation: `core/discovery.py` imports from `adapters/`

**Files:** `src/hyperadmin/core/discovery.py` (delete), `src/hyperadmin/views/dynamic.py` (receive function)

- `build_filter_metadata()` in `core/discovery.py` line 77 imports `adapter_registry` from `adapters/`, violating CONSTITUTION §2 (core must not import from adapters)
- Only consumer: `views/dynamic.py:18`
- Not exported from `core/__init__.py`
- **Fix:** Move `build_filter_metadata()` into `views/dynamic.py` as `_build_filter_metadata()` (private). Delete `core/discovery.py`
- **Risk:** LOW — single call site, mechanical move

## Change 3 — Deduplicate smart defaults resolution

**Files:** `src/hyperadmin/core/introspection.py`, `src/hyperadmin/routing.py`, `src/hyperadmin/core/app.py`

- `routing.py:_resolve_smart_defaults()` (lines 157-195) and `app.py:_auto_register_models()` (lines 210-213) independently call the same 3 `infer_*` functions with identical try/except fallback
- **Fix:**
  1. Add `ResolvedDefaults` frozen dataclass and `resolve_model_defaults()` function to `core/introspection.py`
  2. Replace `_resolve_smart_defaults()` in `routing.py` with call to `resolve_model_defaults()`
  3. Replace inline introspection in `app.py:_auto_register_models()` with `resolve_model_defaults()`
- Also replaces opaque 4-tuple return with named dataclass
- **Risk:** MEDIUM — two callers change, but logic is identical

## Change 4 — Add logging to silent `except Exception` blocks

**Files:** `src/hyperadmin/core/introspection.py` (after Change 3), `src/hyperadmin/views/dynamic.py`

- `resolve_model_defaults()` (moved from routing.py) has 3 bare except blocks that swallow errors silently
- `views/dynamic.py:225` `list_view()` also swallows all errors
- **Fix:** Add `logger.warning(...)` with `exc_info=True` to each block
- **Risk:** VERY LOW — no behavioral change

## Change 5 — Data-driven auth model registration

**File:** `src/hyperadmin/core/app.py`

- `_register_auth_models()` repeats identical check-create-register pattern 3 times (lines 233-252)
- **Fix:** Define `_AUTH_MODELS` list of `(model, name, options)` tuples, loop over it
- **Risk:** VERY LOW — mechanical refactor, identical behavior

---

## Explicitly Skipped

| Finding | Reason |
|---------|--------|
| `create_view`/`update_view` ~85% identical | High risk, deep form handling — separate PR |
| `create_admin_router()` 13 params | Private function, single call site — premature |
| `DynamicModelView.__init__()` 12 params | Same as above, tightly coupled |
| `_register_auth_routes()` 3 closures | Minimal savings (~7 lines), readability cost |
| `core/registry.py` → `adapters/` import | Pre-existing, out of scope |

---

## Implementation Order

**Phase A** (independent, can be parallel): Changes 1A, 1B, 5
**Phase B**: Change 2 (move build_filter_metadata)
**Phase C** (do together): Changes 3 + 4 (dedup + logging)

## Acceptance Criteria

- [ ] `SQLAlchemyAdapter.list()` honors `search_fields` parameter
- [ ] `JsonApiAdapter.list_as_envelope()` forwards `search_fields`
- [ ] `core/discovery.py` deleted, `build_filter_metadata` moved to views layer
- [ ] No `core/` → `adapters/` imports (except pre-existing `core/registry.py`)
- [ ] Smart defaults resolution unified in `core/introspection.py`
- [ ] All bare `except Exception` blocks log warnings
- [ ] Auth model registration is data-driven
- [ ] All 469+ unit tests pass
- [ ] All 62+ E2E tests pass
- [ ] `poe lint` clean (ruff, mypy, basedpyright)
