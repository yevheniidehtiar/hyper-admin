---
type: story
id: eCZImSMiZaIq
title: "feat(ui): add OAuth login buttons to login page"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:templates
  - size:S
  - area:frontend
estimate: null
epic_ref: null
github:
  issue_number: 445
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d7e2daeeddd2652eb14876b3b4582c39f5a97c1c9c749d8c5de72cc9a59df63d
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:41:53Z
updated_at: 2026-04-01T21:41:53Z
---

## Context

The login page currently only shows username/password. When OAuth providers are configured, "Sign in with Google" and "Sign in with GitHub" buttons should appear.

## Scenarios

**Scenario: login page shows configured OAuth provider buttons**
  Given Google and GitHub OAuth providers are configured
  When  GET `/admin/login`
  Then  "Sign in with Google" and "Sign in with GitHub" buttons are visible

**Scenario: login page shows no OAuth buttons when no providers configured**
  Given no OAuth providers are configured
  When  GET `/admin/login`
  Then  only the username/password form is shown

## Acceptance Criteria

- [ ] OAuth provider list passed to login template context via `oauth_providers` global
- [ ] Each provider renders a styled button linking to `/admin/oauth/authorize/{provider}`
- [ ] Buttons show provider name and optional icon
- [ ] Buttons hidden when `oauth_providers` is empty
- [ ] `data-testid="oauth-btn-{provider}"` for E2E
- [ ] No JavaScript required (simple links)

## Files Likely Affected
- `src/hyperadmin/templates/login.html`
- `src/hyperadmin/core/app.py` (pass providers to template globals)

## Dependencies
Depends on: #443 (OAuth routes must exist for the links to work)

## Notes for Implementer
- Add a divider ("or sign in with") between password form and OAuth buttons
- Use `ha-btn` CSS classes for consistent styling
- Provider buttons: `<a href="{{ admin_prefix }}/oauth/authorize/{{ provider.provider_name }}">`
