---
type: story
id: I18nMain_C1A
title: "feat(core): add Babel + locale settings to HyperAdminSettings"
status: done
priority: high
assignee: null
labels:
  - backend
  - i18n
  - size:S
  - cycle:1
estimate: null
epic_ref:
  id: I18nMain_01
github: null
created_at: 2026-05-03T00:00:00Z
updated_at: 2026-05-03T00:00:00Z
---

## Summary

Add the Babel runtime dependency and two locale fields to `HyperAdminSettings`. This
is a pure additive change -- no existing code path is modified. Provides the
configuration surface that C1-B (`LocaleMiddleware`) and C1-C (Jinja loader)
consume.

Spec: `docs/specs/i18n.md`

## Scenarios

**Scenario: default locale is "en" out of the box**
  Given a fresh HyperAdmin install with no env overrides
  When  `HyperAdminSettings()` is instantiated
  Then  `settings.default_locale == "en"`
  And   `settings.supported_locales == ["en","es","fr","de","zh_CN","ja","uk"]`

**Scenario: HYPERADMIN_DEFAULT_LOCALE env override is honored**
  Given environment variable `HYPERADMIN_DEFAULT_LOCALE=es`
  When  `HyperAdminSettings()` is instantiated
  Then  `settings.default_locale == "es"`

**Scenario: HYPERADMIN_SUPPORTED_LOCALES env override is honored**
  Given environment variable `HYPERADMIN_SUPPORTED_LOCALES=en,es,uk`
  When  `HyperAdminSettings()` is instantiated
  Then  `settings.supported_locales == ["en","es","uk"]`

**Scenario: babel is importable at runtime**
  Given the project is installed via `uv sync`
  When  `import babel` is executed
  Then  no ImportError is raised
  And   `babel.__version__` is >= 2.13

## Acceptance criteria

- [ ] `babel>=2.13` added to `[project.dependencies]` in `pyproject.toml`
- [ ] `default_locale: str = "en"` field on `HyperAdminSettings`
- [ ] `supported_locales: list[str] = [...]` field on `HyperAdminSettings` with the 7 locale defaults
- [ ] Both fields documented in the class docstring
- [ ] `uv lock` updated; `poe test:unit` green
- [ ] `from hyperadmin.core.settings import HyperAdminSettings; HyperAdminSettings()` returns object with the new fields

## Files to modify

- `pyproject.toml` -- add `babel>=2.13` to `[project.dependencies]`; run `uv lock`
- `src/hyperadmin/core/settings.py` -- add `default_locale` and `supported_locales` fields

## Implementation notes

- Pydantic-Settings env prefix is already `HYPERADMIN_` -- new fields auto-bind to
  `HYPERADMIN_DEFAULT_LOCALE` and `HYPERADMIN_SUPPORTED_LOCALES`.
- `supported_locales` accepts comma-separated env values via Pydantic's default
  list parsing.
- No changes to `Admin.__init__` in this story; that wiring belongs to C1-B/C1-C.
- This story unblocks C1-B and C1-C in parallel.

## Demo checkpoint

```python
import os
os.environ["HYPERADMIN_DEFAULT_LOCALE"] = "es"
from hyperadmin.core.settings import HyperAdminSettings
print(HyperAdminSettings().default_locale)  # "es"
```

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** Cycle 0 SDD approval (PR #516 merged)
