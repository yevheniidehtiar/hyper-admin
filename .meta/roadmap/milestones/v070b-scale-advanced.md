---
type: milestone
id: v070b-scale-02
title: "v0.7.0b — Scale Advanced"
status: todo
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

**Roadmap position 13/16 (2026-09-28 re-cut).** The 10M+ rows / 100 req/s tail of the original v0.7.0: keyset (cursor) pagination (A4, `epic-v070b-keyset-cursor-pagination`, #226–#230), engine pool configuration and rate limiting (epic #212), and the E2E scalability validation + configuration guide (epic #214).

v0.7.1 (Locust load testing + synthetic data) is the measurement harness for
this milestone and follows it in roadmap order; the synthetic data generator
already shipped (PR #570) and the Locust suite is in open PR #572.
