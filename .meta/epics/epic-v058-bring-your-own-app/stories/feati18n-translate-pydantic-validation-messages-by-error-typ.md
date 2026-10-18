---
type: story
id: st-v058-byoa-27
title: "feat(i18n): translate Pydantic validation messages by error type (#531)"
status: done
priority: high
assignee: null
labels:
  - size:M
  - area:i18n
  - layer:logic
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-10-17T00:00:00Z
---

## Scope change (2026-10-18)

Originally deferred out of v0.5.8 (Owner decision 8, 2026-10-08). It was built anyway as PR #624, and the
owner chose to merge it into v0.5.8 on 2026-10-18. The `deferred` label is removed and the story is done.

## Summary

Add `i18n/validation_messages.translate_error`, which maps about 25 pydantic error types to msgids marked with `gettext_noop` and `%(ctx)s` placeholders. Use it at `views/forms.py:494,716` and `views/dynamic.py:1545`, and add Ukrainian translations.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: D.4

## Files to Change

- `src/hyperadmin/i18n/validation_messages.py`
- `src/hyperadmin/i18n/__init__.py`
- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/views/dynamic.py`
- `messages.pot`
- `src/hyperadmin/locale/uk/LC_MESSAGES/messages.po`
- `tests/unit/test_validation_messages_i18n.py`

## Scenarios

```
Scenario: validation message is translated
  Given locale 'uk'
  And   a field constrained gt=5
  When  3 is submitted
  Then  the field error shows the Ukrainian 'greater than 5' message

Scenario: unknown type falls back
  Given an unmapped error type
  When  translate_error runs
  Then  the original msg is returned
```

## Acceptance Criteria

- [ ] validation message is translated
- [ ] unknown type falls back
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- **Deferral candidate** (Owner decision 8). Nothing on the critical path depends on this story.

## Blocked by

- `reviewspec-approve-byoa-sdd` (st-v058-byoa-00)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
