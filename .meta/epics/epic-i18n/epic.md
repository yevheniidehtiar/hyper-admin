---
type: epic
id: I18nMain_01
title: "epic(i18n): Internationalization -- gettext + Babel + RTL + 7 locales"
status: in_progress
priority: high
owner: null
labels:
  - i18n
  - backend
  - frontend
  - css
milestone_ref:
  id: ulcysRt0fus6
github: null
created_at: 2026-05-03T00:00:00Z
updated_at: 2026-05-03T00:00:00Z
---

## Epic: Internationalization -- gettext + Babel + RTL

Part of milestone: **v0.4.1 -- i18n** (target: 2026-07-30)

**Spec:** `docs/specs/i18n.md`

### Goal

Make HyperAdmin localizable end-to-end: every UI string is translatable via gettext,
runtime locale is detected per-request (cookie > Accept-Language > settings default),
users can switch locale from the navbar, the layout supports RTL via logical CSS
properties, and 7 seed locales (en, es, fr, de, zh_CN, ja, uk) ship with empty catalogs
ready for community translation. English remains the only fully-translated locale at
release; other catalogs are scaffolded for follow-up.

### Principles

1. **Babel + jinja2.ext.i18n** -- canonical Python i18n stack, no custom invention.
2. **Cookie-driven locale** -- no URL-prefix routing changes; mirrors the auth-cookie pattern.
3. **Logical CSS only** -- physical properties (`margin-right`, `text-align: left`) become
   logical (`margin-inline-end`, `text-align: start`); RTL is structural, not bolted on.
4. **Backward compatible** -- existing apps default to `en` and render identically.
5. **Bottom-up** -- deps + settings -> middleware -> Jinja loader -> wrap strings ->
   switcher -> RTL -> catalogs -> tests.

### 3-Cycle Delivery Plan (zero file conflict per cycle)

#### Cycle 0 -- SDD (1 chore-pm, human gate)

| Slot | Story | Size |
|------|-------|------|
| C0   | chore(pm): create i18n SDD + epic | S |

Human gate: `review(spec): approve SDD for i18n` -- blocks all C1+ stories.

#### Cycle 1 -- Foundations

| Slot | Story | Size | Files |
|------|-------|------|-------|
| C1-A | feat(core): add Babel + locale settings to HyperAdminSettings | S | `pyproject.toml`, `src/hyperadmin/core/settings.py` |
| C1-B | feat(core): LocaleMiddleware (cookie > Accept-Language > default) | M | `src/hyperadmin/i18n/__init__.py` (new), `src/hyperadmin/i18n/middleware.py` (new), `src/hyperadmin/core/app.py` (wire) |
| C1-C | feat(core): wire jinja2.ext.i18n + per-request Translations | M | `src/hyperadmin/i18n/loader.py` (new), `src/hyperadmin/core/app.py` (extend Jinja env) |

Conflict check: A+B disjoint -> parallel. C touches `app.py` near the same Jinja init
block as B, sequence C after B merges.

#### Cycle 2 -- Strings + switcher

| Slot | Story | Size | Files |
|------|-------|------|-------|
| C2-A | refactor(ui): wrap login/navbar/sidebar/messages in `_()` | S | `templates/login.html`, `_navbar.html`, `_sidebar.html`, `_messages.html` |
| C2-B | refactor(ui): wrap list/detail/form/pagination/components | M | `templates/list_layout.html`, `detail.html`, `create.html`, `update.html`, `form_layout.html`, `pagination.html`, `components/*` |
| C2-C | feat(views): structured flash + translatable validation messages | M | `src/hyperadmin/views/static.py`, `src/hyperadmin/views/forms.py` |
| C2-D | feat(ui): locale switcher in navbar + POST endpoint sets cookie | M | `templates/_navbar.html` (rebase on C2-A), `static/css/_navbar.css`, `src/hyperadmin/views/locale.py` (new) |
| C2-E | feat(core): translatable model verbose names + field labels | M | `src/hyperadmin/core/options.py`, `src/hyperadmin/core/registry.py` |

Conflict check: A/B/C/E disjoint -> parallel. C2-D rebases on C2-A (both touch
`_navbar.html`).

#### Cycle 3 -- RTL + catalogs + tests

| Slot | Story | Size | Files |
|------|-------|------|-------|
| C3-A | refactor(ui): physical -> logical CSS properties | M | all `src/hyperadmin/static/css/*.css` |
| C3-B | feat(ui): `<html dir>` from locale + `_rtl.css` overrides | S | `templates/_base.html`, `static/css/_rtl.css` (new), `static/css/main.css` (import) |
| C3-C | feat(build): Babel extraction + 7 locale catalogs + poe targets | M | `babel.cfg` (new), `src/hyperadmin/locale/<locale>/LC_MESSAGES/messages.po` x 7, `pyproject.toml` |
| C3-D | test(unit): LocaleMiddleware + Translations loader | M | `tests/unit/test_i18n_middleware.py`, `tests/unit/test_i18n_loader.py` |
| C3-E | test(e2e): locale switcher + RTL layout snapshot | M | `tests/e2e/test_i18n.py` |

Conflict check: C3-A/C3-B both touch CSS -- A finishes the logical-property refactor,
B layers RTL-specific overrides; sequence A -> B. C3-C/D/E parallel after C3-A.

### Sub-issues (14 stories: 1 chore-pm + 13 feat/test)

| Cycle | Story | Size | Depends on |
|-------|-------|------|-----------|
| C0    | chorepm-create-i18n-sdd | S | none |
| C1-A  | feat-core-babel-locale-settings | S | SDD approved |
| C1-B  | feat-core-locale-middleware | M | SDD approved |
| C1-C  | feat-core-jinja-i18n-loader | M | C1-B |
| C2-A  | refactorui-wrap-login-navbar-sidebar | S | C1-C |
| C2-B  | refactorui-wrap-list-detail-form | M | C1-C |
| C2-C  | featviews-translatable-validation | M | C1-C |
| C2-D  | featui-locale-switcher | M | C2-A |
| C2-E  | featcore-translatable-model-verbose | M | C1-C |
| C3-A  | refactorui-logical-css-properties | M | none (independent) |
| C3-B  | featui-html-dir-rtl-overrides | S | C3-A, C2-D |
| C3-C  | featbuild-babel-extract-7-catalogs | M | all C2 wrap-string stories |
| C3-D  | testunit-i18n-middleware-loader | M | C1-B, C1-C |
| C3-E  | teste2e-locale-switcher-rtl | M | all C3 |

### Critical Path

```
C1-B (middleware, M) -> C1-C (loader, M) -> C2-D (switcher, M) -> C3-B (RTL, S) -> C3-E (e2e, M)
```

### Acceptance Criteria

- [ ] SDD at `docs/specs/i18n.md` reviewed and approved
- [ ] Babel + locale settings wired into `HyperAdminSettings`
- [ ] LocaleMiddleware resolves locale per request (cookie > Accept-Language > default)
- [ ] Jinja templates render via `jinja2.ext.i18n` with per-request `Translations`
- [ ] All 38 hardcoded UI strings wrapped in `_()` / `{% trans %}`
- [ ] Locale switcher in navbar sets `hyperadmin_locale` cookie
- [ ] Model verbose names and field labels translatable
- [ ] All CSS uses logical properties; `_rtl.css` overrides where needed
- [ ] `<html dir>` driven by locale; RTL layout mirrors LTR at all breakpoints
- [ ] 7 locale catalogs scaffolded under `src/hyperadmin/locale/`
- [ ] `poe i18n:extract` and `poe i18n:compile` targets work
- [ ] Unit + E2E tests cover middleware, loader, switcher, and RTL
