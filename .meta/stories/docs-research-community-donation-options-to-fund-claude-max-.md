---
type: story
id: fuJpJRV4Ly6k
title: "docs: research community donation options to fund Claude Max subscription"
status: todo
priority: medium
assignee: null
labels:
  - documentation
estimate: null
epic_ref: null
github:
  issue_number: 279
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:bbd887d89f8de925335bbcda0b0459903e66790786f2b8a5a7572d49e639dc82
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T09:41:04Z
updated_at: 2026-03-27T09:41:04Z
---

## Context

HyperAdmin's agentic workflow relies on Claude Max subscription (~\$100/month) for its
autonomous development pipeline (conductor, dev agents, reviewer, delivery manager).
As the project grows and community contributions increase, community funding could offset
this cost and make the workflow sustainable long-term.

This is a **research task** — output should be a summary comment on this issue or a new
docs page at `docs/community/donations.md`.

## Research Goals

- [ ] Survey donation platforms: GitHub Sponsors, Open Collective, Ko-fi, Buy Me a Coffee, Polar.sh
- [ ] Compare on: platform fees, payout schedule, tax/legal implications (EU/US), badge integration with repo
- [ ] Evaluate GitHub Sponsors specifically — zero fees, native repo integration, Stripe-backed
- [ ] Determine minimum viable setup: which platform to start with, what tiers, what perks
- [ ] Research whether accepting donations affects OSS license obligations (MIT)
- [ ] Identify comparable OSS AI projects that fund GPU/API costs via donations (learn from them)

## Proposed Sponsor Tiers (draft — adjust based on research)

| Tier | Amount | Perk |
|------|--------|------|
| Supporter | \$5/month | Name in CONTRIBUTORS |
| Backer | \$20/month | Name in README sponsors section |
| Sponsor | \$100/month | Covers one month of Claude Max — logo in README |
| Patron | \$200/month | Direct input on roadmap priorities |

## Acceptance Criteria

- [ ] Comparison table of 3+ platforms with pros/cons
- [ ] Clear recommendation with rationale
- [ ] Draft `FUNDING.yml` content ready to commit
- [ ] Draft sponsor tier descriptions (can refine the table above)
- [ ] Summary of any legal/license considerations

## Notes

Do not implement payment setup — research and document only.
