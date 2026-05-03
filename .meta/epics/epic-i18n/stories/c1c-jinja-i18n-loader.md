---
type: story
id: I18nMain_C1C
title: "feat(core): wire jinja2.ext.i18n + per-request Translations loader"
status: todo
priority: high
assignee: null
labels:
  - backend
  - i18n
  - size:M
  - cycle:1
estimate: null
epic_ref:
  id: I18nMain_01
github: null
created_at: 2026-05-03T00:00:00Z
updated_at: 2026-05-03T00:00:00Z
---

## Summary

Wire `jinja2.ext.i18n` into the Admin Jinja environment and install
`babel.support.Translations` per request via a context processor. Templates can now
call `{{ _("Save") }}` and `{% trans %}...{% endtrans %}`.

Spec: `docs/specs/i18n.md`

## Scenarios

**Scenario: gettext is bound on the Jinja env**
  Given an Admin app
  When  a template `{{ _("Save") }}` renders for locale "en" with no catalog yet
  Then  the rendered output is "Save" (msgid passthrough)
  And   no exception is raised

**Scenario: per-request Translations is installed**
  Given an Admin app and a Spanish .mo file for msgid "Save" -> "Guardar"
  When  a request with request.state.locale=="es" renders `{{ _("Save") }}`
  Then  the rendered output is "Guardar"

**Scenario: missing catalog falls back without error**
  Given supported_locales includes "ja" but its .mo file is missing
  When  a request resolves to locale "ja" and renders `{{ _("Save") }}`
  Then  the rendered output is "Save"
  And   a warning is logged once per process

**Scenario: ngettext plural works**
  Given a Spanish catalog with plural form for "{n} item"/"{n} items"
  When  template `{{ ngettext("{n} item", "{n} items", 2).format(n=2) }}` renders for locale "es"
  Then  the output is the plural Spanish form

**Scenario: error-handler render with no LocaleMiddleware does not crash**
  Given a request that fails before LocaleMiddleware runs
  When  the error handler renders a template using `{{ _("Error") }}`
  Then  the output is "Error" (NullTranslations fallback)
  And   no exception is raised

## Acceptance criteria

- [ ] `src/hyperadmin/i18n/loader.py` exposes `load_translations(locale: str) -> babel.support.Translations`
- [ ] LRU-cached per-locale; thread-safe; gracefully returns `NullTranslations` on missing/corrupt `.mo`
- [ ] `Admin.__init__` adds `jinja2.ext.i18n` to the Jinja env extensions
- [ ] Context processor installs `request.state.translations` (or `NullTranslations`) into the env per request
- [ ] Jinja globals `_`, `gettext`, `ngettext`, `pgettext` available in all templates
- [ ] Logging: missing catalog warning emitted once per locale per process
- [ ] Unit test scaffolding for loader (full tests live in C3-D)

## Files to modify

- `src/hyperadmin/i18n/__init__.py` -- export `load_translations`, `gettext_lazy`
- `src/hyperadmin/i18n/loader.py` (new) -- `load_translations`, `gettext_lazy`
- `src/hyperadmin/core/app.py` -- extend Jinja env with `jinja2.ext.i18n` and register context processor

## Implementation notes

- `babel.support.Translations.load(dirname, locales=[locale], domain="messages")` is
  the canonical loader; wrap in `functools.lru_cache(maxsize=32)`.
- `gettext_lazy` proxy: a small class with `__str__` deferring to
  `babel.support.LazyProxy` or the equivalent Django-style `lazy` pattern. Required
  for class-body model metadata (C2-E).
- Context processor must read `getattr(request.state, "locale", settings.default_locale)`
  -- error handlers may not have `LocaleMiddleware` state.
- `Admin.__init__` already constructs the Jinja env at `core/app.py:82` -- extend
  there, do not introduce a second env.
- Coordinate with C1-B: both stories edit `core/app.py` in the same region. C1-C
  rebases on C1-B's merge.

## Demo checkpoint

```python
from hyperadmin import Admin
from sqlmodel import create_engine
admin = Admin(create_engine("sqlite:///:memory:"))
env = admin.app.state.jinja_env  # or wherever stored
assert "jinja2.ext.InternationalizationExtension" in {ext.identifier for ext in env.iter_extensions()}
tmpl = env.from_string("{{ _('Save') }}")
print(tmpl.render())  # "Save"
```

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** C1-B (both stories edit `core/app.py` near the Jinja init block; C1-B merges first)
