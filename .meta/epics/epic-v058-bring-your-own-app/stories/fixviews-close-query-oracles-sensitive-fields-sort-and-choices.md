---
type: story
id: st-v058-byoa-53
title: "fix(views): close query oracles — sensitive fields, sort_by whitelist, choices cascade whitelist"
status: todo
priority: critical
assignee: null
labels:
  - size:M
  - planned
  - area:views
  - layer:views
  - security
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Four query paths let a user probe secret columns such as `password_hash`, and `detail_view` shows them outright. The same holds for a host `User` model registered through `auto_discover` in bridge mode. This is a bug fix (Owner decisions 4 and 7), so it is **not blocked by the SDD gate**.

- **Search.** `infer_search_fields` includes every `str` field (`core/introspection.py:168-183`), so `?search=` is an ilike substring oracle.
- **Sort.** `sort_by` is passed unvalidated to `getattr(self.model, order_by)` (`views/dynamic.py:243,272`; `adapters/sqlmodel.py:96-99`). That is an ordering oracle, and an unknown value raises `AttributeError`.
- **Detail.** `detail_view` dumps every column (`views/dynamic.py:379`, `detail.html:7`).
- **Choices.** `choices_view` forwards every extra query parameter as an equality filter on the target model (`views/dynamic.py:925-930`, `adapters/sqlmodel.py:240-245`), and never applies the target admin's `get_queryset`.

Fix:
- Add `core/sensitive.is_sensitive(name, field_info)`. It is true for the marker `json_schema_extra={"hyperadmin_sensitive": True}`, or for names matching `(^|_)(password|secret|token|hash)(_|$)`. `AdminOptions.sensitive_fields` overrides it in either direction.
- Exclude sensitive fields from inferred search, inferred `column_list`, detail, filters and sorting. On forms they are write-only: an empty submission keeps the stored value.
- Mark `auth/models.User.password_hash` as sensitive.
- Whitelist `sort_by` against the sortable displayed columns. An unknown or sensitive value falls back to the default sort, and the page returns 200.
- In the choices endpoint, forward only the cascade keys declared by the relation widget (`dependent_on`), and apply the target admin's `get_queryset`. The target-model view check is in `-10`.
- Add a changelog security note listing all four oracles.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — sections: D.2, D.3, Owner decision 7

## Files to Change

- `src/hyperadmin/core/sensitive.py` (new)
- `src/hyperadmin/core/introspection.py`
- `src/hyperadmin/core/options.py` (`sensitive_fields`)
- `src/hyperadmin/views/dynamic.py`
- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/adapters/sqlmodel.py`, `src/hyperadmin/adapters/sqlalchemy.py` (`get_choices`)
- `src/hyperadmin/auth/models.py`
- `tests/unit/test_query_oracles.py`

## Scenarios

```
Scenario: unknown sort_by falls back to the default sort
  Given Order is registered
  When  the user requests /admin/order?sort_by=nope
  Then  the response status is 200
  And   the rows are in the default order

Scenario: sort_by on a sensitive field is ignored
  When  the user requests /admin/user?sort_by=password_hash
  Then  the rows are in the default order

Scenario: search does not match sensitive fields
  Given User rows whose password_hash contains "abc" and whose other fields do not
  When  the user requests /admin/user?search=abc
  Then  no users are listed

Scenario: detail page hides sensitive fields
  Given a User row
  When  the user opens its detail page
  Then  the detail-fields container has no password_hash entry

Scenario: choices ignore undeclared cascade parameters
  Given Order.customer is an FK to User with no declared cascade
  When  GET /admin/order/choices/customer?password_hash=abc is requested
  Then  every User visible to the requester is returned

Scenario: choices apply the target admin queryset
  Given the User admin's get_queryset hides inactive users
  When  GET /admin/order/choices/customer is requested
  Then  no inactive user is offered
```

## Acceptance Criteria

- [ ] Every scenario above has a passing test
- [ ] The changelog has a security note covering filters, search, sort and choices
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- None. This is a standalone security fix (Owner decision 4), so it is not gated by `st-v058-byoa-00`.

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
