---
type: milestone
id: v060a-occ-01
title: "v0.6.0a — Optimistic Concurrency Control"
status: done
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-11-20T00:00:00Z
---

**Roadmap position 4/16 (2026-09-28 re-cut).** Split out of v0.6.0 (Real-Time Layer). OCC has no dependency on pub/sub: a version column, `StaleRecordError`, a hidden `__version` field on update forms and a conflict dialog. Lost-update protection is table stakes for teams running the admin against a live production app.

Epic 6.2.3 (#332), stories #314–#321. Spec: `docs/specs/realtime-occ.md`.

**Delivered (2026-11-11).** Epic #332 and stories #314–#321 are merged and closed.
