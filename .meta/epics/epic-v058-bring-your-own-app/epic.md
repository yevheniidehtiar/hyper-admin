---
type: epic
id: ep-v058-byoa-01
title: "epic(core): Bring Your Own App — mount into an existing FastAPI app without taking over"
status: todo
priority: critical
owner: null
labels:
  - planned
  - area:core
  - dogfood
  - size:L
milestone_ref:
  id: v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Overview

Make HyperAdmin the admin you add to an existing FastAPI app in about 10 minutes, with fewer than 20 lines of code,
without it taking over the app: your models, your UUID and string keys, your migrations, your engine, your auth.

**Spec**: [docs/specs/bring-your-own-app.md](../../../docs/specs/bring-your-own-app.md) (Status: Draft; the first story is its human gate)

## Pillars

- **A. Keys & datetimes:** `PrimaryKeyInfo` via mapper introspection; pk-aware routes, adapters, views and templates;
  `core/timezones.py`; `UTCNaiveDateTime` for the auth models; the `sqlmodel<0.0.45` cap is removed.
- **B. Auth bridge:** `Admin(auth=ExternalAuth(get_user=<host Depends>))`; a route-level dependency plus the
  `HyperAdminRoute` class; built-in auth models become opt-in; lazy `auth` imports; the token-cookie handoff.
- **C. Non-invasive mount:** an isolated sub-app, a public lifecycle API, opt-in DDL (`hyperadmin init-db`),
  `session_factory`, a lazy default engine, an admin-scoped session cookie, and uploads served behind auth.
- **D. Hardening:** signed double-submit CSRF; `list_view` shows errors; typed, whitelisted filters;
  validation messages through gettext (#531).
- **E. Packaging & release:** a dependency audit, a committed `uv.lock`, version `0.5.0a1` on PyPI, and
  working release and publish workflows.

## Out of scope

- A plain SQLAlchemy `DeclarativeBase` adapter (deferred).
- Composite primary keys (registered list-only, with a warning).
- OAuth SSO itself (v0.5.2).
- Moving built-in auth off middleware.

## Stories (bottom-up)

| ID | Story | Size | Blocked by |
|---|---|---|---|
| st-v058-byoa-00 | [review(spec): approve BYOA SDD](stories/reviewspec-approve-byoa-sdd.md) | S | — |
| st-v058-byoa-10 | [fix(views): enforce permissions and row scoping on item, inline, bulk, file and choices handlers](stories/fixviews-enforce-model-and-object-permissions-on-inline-edit.md) | M | — (security fix, not gated) |
| st-v058-byoa-11 | [chore(deps): audit runtime dependencies](stories/choredeps-audit-runtime-dependencies.md) | S | byoa-00 |
| st-v058-byoa-12 | [build: commit uv.lock, enforce uv sync --locked in CI and gate PRs to master/develop](stories/build-commit-uv-lock-enforce-uv-sync-locked-in-ci-and-gate-p.md) | S | byoa-11 |
| st-v058-byoa-13 | [feat(core): PrimaryKeyInfo codec, InvalidPrimaryKey and BaseAdapter.pk/datetime_kind](stories/featcore-primarykeyinfo-codec-invalidprimarykey-and-baseadap.md) | S | byoa-00 |
| st-v058-byoa-14 | [feat(core): timezones module and settings.timezone](stories/featcore-timezones-module-and-settings-timezone.md) | M | byoa-00 |
| st-v058-byoa-15 | [feat(adapters): introspection of primary keys, datetime kinds and column value coercion](stories/featadapters-introspection-of-primary-keys-datetime-kinds-an.md) | M | byoa-13, byoa-14 |
| st-v058-byoa-16 | [fix(auth): tz-aware auth model timestamps via UTCNaiveDateTime and utc_now](stories/fixauth-tz-aware-auth-model-timestamps-via-utcnaivedatetime.md) | S | byoa-14 |
| st-v058-byoa-17 | [refactor(auth): lazy auth package exports and auth.metadata()](stories/refactorauth-lazy-auth-package-exports-and-auth-metadata.md) | S | byoa-00 |
| st-v058-byoa-18 | [feat(core): admin auth exceptions and pure CsrfTokenSigner](stories/featcore-admin-auth-exceptions-and-pure-csrftokensigner.md) | S | byoa-00 |
| st-v058-byoa-19 | [feat(core): typed filter coercion and FilterCondition](stories/featcore-typed-filter-coercion-and-filtercondition.md) | M | byoa-14 |
| st-v058-byoa-20 | [refactor(db): lazy default engine; deprecate hyperadmin.db.engine](stories/refactordb-lazy-default-engine-deprecate-hyperadmin-db-engin.md) | S | byoa-00 |
| st-v058-byoa-21 | [feat(core): session_factory seam on BaseAdapter, adapters and auth services](stories/featcore-session-factory-seam-on-baseadapter-adapters-and-au.md) | M | byoa-20 |
| st-v058-byoa-22 | [refactor(adapters): pk-agnostic get/get_related/update/delete/get_choices/save_inline_rows](stories/refactoradapters-pk-agnostic-get-get-related-update-delete-g.md) | M | byoa-15, byoa-21 |
| st-v058-byoa-23 | [refactor(core): pk-aware display name, FK filter choices, list_display fallback and inline display fields](stories/refactorcore-pk-aware-display-name-fk-filter-choices-list-di.md) | S | byoa-13 |
| st-v058-byoa-24 | [feat(adapters): apply FilterCondition lists with dict back-compat](stories/featadapters-apply-filtercondition-lists-with-dict-back-comp.md) | S | byoa-19, byoa-22 |
| st-v058-byoa-25 | [feat(auth): ExternalAuth, TokenCookie, CallablePermissionChecker and build_admin_dependency](stories/featauth-externalauth-tokencookie-callablepermissionchecker.md) | M | byoa-17, byoa-18 |
| st-v058-byoa-26 | [feat(core): lifecycle with opt-in create_tables, startup/shutdown/lifespan, first-request guard and init-db CLI](stories/featcore-lifecycle-with-opt-in-create-tables-startup-shutdow.md) | M | byoa-17, byoa-21 |
| st-v058-byoa-27 † | [feat(i18n): translate Pydantic validation messages by error type (#531)](stories/feati18n-translate-pydantic-validation-messages-by-error-typ.md) | M | byoa-00 |
| st-v058-byoa-28 | [feat(routing): per-model pk convertor, hyperadmin_pk convertor, literal routes first, composite list-only](stories/featrouting-per-model-pk-convertor-hyperadmin-pk-convertor-l.md) | M | byoa-15 |
| st-v058-byoa-29 | [refactor(views): DynamicModelView item handlers use self.pk and _resolve_pk](stories/refactorviews-dynamicmodelview-item-handlers-use-self-pk-and.md) | M | byoa-10, byoa-22, byoa-23, byoa-28 |
| st-v058-byoa-30 | [refactor(views): bulk ids, single actions and popup payload are pk-type-agnostic](stories/refactorviews-bulk-ids-single-actions-and-popup-payload-are.md) | S | byoa-29 |
| st-v058-byoa-31 | [refactor(forms): pk-aware PydanticForm and InlineFormset pk codec](stories/refactorforms-pk-aware-pydanticform-and-inlineformset-pk-cod.md) | M | byoa-29 |
| st-v058-byoa-32 | [feat(forms): tz-aware datetime parsing, Aware/NaiveDatetime widgets, broader auto-now detection, preserve unchanged values](stories/featforms-tz-aware-datetime-parsing-aware-naivedatetime-widg.md) | M | byoa-31 |
| st-v058-byoa-33 | [feat(views): template filters ha_pk/ha_dom_token/ha_datetime_input/ha_display and timezone plumbing](stories/featviews-template-filters-ha-pk-ha-dom-token-ha-datetime-in.md) | S | byoa-13, byoa-14 |
| st-v058-byoa-34 | [feat(views): namespace-aware url helper and Jinja url_for override](stories/featviews-namespace-aware-url-helper-and-jinja-url-for-overr.md) | S | byoa-00 |
| st-v058-byoa-35 | [feat(core): isolated sub-application mount](stories/featcore-isolated-sub-application-mount.md) | M | byoa-26, byoa-30, byoa-34 |
| st-v058-byoa-36 | [feat(auth): admin-scoped session cookie via AdminSessionMiddleware](stories/featauth-admin-scoped-session-cookie-via-adminsessionmiddlew.md) | M | byoa-35 |
| st-v058-byoa-37 | [fix(uploads): serve files per record behind permission, object and queryset checks](stories/fixuploads-serve-uploads-under-the-admin-prefix-behind-auth.md) | M | byoa-10, byoa-35 |
| st-v058-byoa-38 | [feat(views): HyperAdminRoute route class with auth-error translation and token-cookie bridging](stories/featviews-hyperadminroute-route-class-with-auth-error-transl.md) | M | byoa-18, byoa-35 |
| st-v058-byoa-39 | [feat(views): CsrfGuard signed double-submit with proxy-safe Origin check and token injection](stories/featviews-csrfguard-signed-double-submit-wired-into-hyperadm.md) | M | byoa-38 |
| st-v058-byoa-40 | [feat(core): Admin(auth=ExternalAuth) wiring and opt-in built-in auth models](stories/featcore-adminauth-externalauth-wiring-and-opt-in-built-in-a.md) | M | byoa-25, byoa-39 |
| st-v058-byoa-41 | [feat(auth): token handoff, bearer login form, JWT-exp cookie lifetime and bridge logout](stories/featauth-token-handoff-post-auth-session-and-bridge-logout.md) | M | byoa-40 |
| st-v058-byoa-42 | [feat(realtime): hashable user keys, bridge-aware SSE/WS and WebSocket Origin check](stories/featrealtime-hashable-user-keys-bridge-aware-sse-ws-and-webs.md) | S | byoa-40 |
| st-v058-byoa-43 | [fix(views): list_view logs and surfaces DB errors instead of swallowing them](stories/fixviews-list-view-logs-and-surfaces-db-errors-instead-of-sw.md) | S | byoa-29, byoa-53 |
| st-v058-byoa-44 | [feat(views): typed, whitelisted filters in list_view](stories/featviews-typed-whitelisted-filters-in-list-view.md) | S | byoa-24, byoa-43 |
| st-v058-byoa-45 | [feat(templates): pk-agnostic item links/testids and tz-aware datetime rendering](stories/feattemplates-pk-agnostic-item-links-testids-and-tz-aware-da.md) | M | byoa-32, byoa-33 |
| st-v058-byoa-46 | [feat(ui): bridge-aware navbar and CSRF reload banner](stories/featui-csrf-token-injection-and-bridge-aware-navbar.md) | S | byoa-40 |
| st-v058-byoa-47 † | [feat(ui): range inputs and filter errors in the filter bar](stories/featui-range-inputs-and-filter-errors-in-the-filter-bar.md) | M | byoa-44 |
| st-v058-byoa-48 | [build(deps): lift the sqlmodel<0.0.45 cap and migrate examples and fixtures to utc_now](stories/builddeps-lift-the-sqlmodel-0-0-45-cap-and-migrate-examples.md) | S | byoa-16, byoa-32, byoa-45 |
| st-v058-byoa-49 | [test(e2e): pk-type and timezone fixture app (UUID, natural str, int)](stories/teste2e-pk-type-and-timezone-fixture-app-uuid-natural-str-in.md) | M | byoa-30, byoa-45, byoa-48 |
| st-v058-byoa-50 | [build(release): 0.5.0a1, pep440 commitizen, __version__ and fixed release/publish workflows](stories/buildrelease-0-5-0a1-pep440-commitizen-version-and-fixed-rel.md) | M | byoa-12, byoa-48 |
| st-v058-byoa-51 | [docs(guides): existing-app guide, examples/byoa, CSRF upgrade note and multi-tenancy SDD amendment](stories/docsguides-existing-app-guide-examples-byoa-csrf-upgrade-not.md) | M | byoa-36, byoa-37, byoa-41, byoa-42, byoa-46, byoa-49 |
| st-v058-byoa-52 | [chore(dogfood): dogfood-1 on a real existing app from the PyPI alpha; gap log](stories/choredogfood-dogfood-1-on-a-real-existing-app-from-the-pypi.md) | S | byoa-50, byoa-51, byoa-54 |
| st-v058-byoa-53 | [fix(views): close query oracles — sensitive fields, sort_by whitelist, choices cascade whitelist](stories/fixviews-close-query-oracles-sensitive-fields-sort-and-choices.md) | M | — (security fix, not gated) |
| st-v058-byoa-54 | [chore(dogfood): dogfood-0 from a repository install once the bridge and isolated mount land](stories/choredogfood-dogfood-0-from-a-repository-install.md) | S | byoa-35, byoa-41 |

† Deferral candidate under Owner decision 8 (off the critical path).

These supersede the re-cut stubs `st-v058-byoa-01` to `-07` on `chore/meta-roadmap-recut`. When that branch merges,
delete the stub story files and keep this `epic.md`.

## Acceptance

- [ ] An existing FastAPI app with Alembic migrations, UUID keys and its own JWT auth mounts the admin in fewer than 20 lines
- [ ] No DDL runs against the host database unless it is explicitly requested
- [ ] Full CRUD, inlines, actions, bulk actions, popups and file fields work with UUID and natural-string keys (unit and E2E)
- [ ] Int-`id` users see identical URLs and `data-testid`s
- [ ] Works on sqlmodel 0.0.19 through the latest release (the cap is removed)
- [ ] CSRF protects every unsafe admin request, including behind a TLS-terminating proxy
- [ ] No handler bypasses model, object or queryset scoping; no query parameter is an oracle on sensitive fields
- [ ] `hyper-admin==0.5.0a1` installs from PyPI and `from hyperadmin import Admin` works
- [ ] The guide can be followed start to finish in 10 minutes or less on a clean checkout
- [ ] The dogfood-1 gap log has been reviewed, and blocking gaps are fixed in this milestone

## Parent

- Milestone: `v058-byoa-01` (v0.5.8 — Bring Your Own App, dogfood-1)
