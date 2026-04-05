---
type: story
id: EGUr8p0L_Ny5
title: "review(spec): approve SDD for OAuth SSO"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:auth
  - size:S
  - needs-human
estimate: null
epic_ref:
  id: ufsAiAiHcy3m
github:
  issue_number: 438
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:52ece39db29aa0e4b746d637515df44e33b1785267964baf5e3eb3b330cedce5
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:40:08Z
updated_at: 2026-04-01T21:40:08Z
---

## Context

Human gate for Epic #420. The SDD at `docs/specs/oauth-sso.md` must be reviewed and approved before OAuth implementation begins. This epic introduces a new auth domain (OAuth) touching auth/, core/, views/.

## Acceptance Criteria

- [ ] SDD file exists at `docs/specs/oauth-sso.md`
- [ ] Problem statement is clear and scoped
- [ ] Goals are measurable, non-goals prevent over-engineering (no SAML, no session revocation)
- [ ] BDD scenarios cover happy path + failure paths for OAuth flow
- [ ] OAuthToken data model documented
- [ ] OAuthProviderConfig documented with Google and GitHub specifics
- [ ] Edge cases: expired tokens, revoked access, duplicate email provisioning
- [ ] Open questions resolved
- [ ] Status changed from Draft to Approved

## Files Likely Affected
- `docs/specs/oauth-sso.md` (new)

## Dependencies
Depends on: Epic #419 complete (AuthBackend protocol stable)

## Notes for Implementer
- SDD template: `docs/specs/TEMPLATE.md`
- Must address: What happens if OAuth email matches existing local user?
- Must address: Token storage security (encryption at rest?)
