---
type: epic
id: SnjolGjNN_F7
title: "epic: Synthetic Data Generator (Faker + bulk inserts for 10M+ records)"
status: done
priority: medium
owner: null
labels:
  - area:examples
  - performance
  - area:loadtest
milestone_ref:
  id: c-zG_jh0ymKJ
github:
  issue_number: 246
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:932a5b926b77921edf3beb4aadd909db1e5d06ff09a7d6a77c876c8768367f60
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:05:09Z
updated_at: 2026-06-03T00:00:00Z
---

## Overview
Bulk data seeder using Faker + SQLAlchemy Core batched inserts with FK pool management and Pareto distribution. Targets 50K-100K inserts/sec on PostgreSQL.

## Sub-issues
- #248 test: unit tests for bulk insert batch generator
- #249 feat(loadtest): batch data generator with Faker + SQLAlchemy Core
- #250 test: unit tests for FK relationship pool and Pareto distribution
- #251 feat(loadtest): FK ID pool manager with Pareto distribution
- #252 test: unit tests for progress reporting and resumable seeding
- #253 feat(loadtest): Rich progress bar and resumable seeding
- #254 feat(loadtest): Typer CLI `hyperadmin seed` subcommand
- #255 test: integration test — seed 1K records, verify FK integrity
- #256 refactor(examples): migrate seed.py to use bulk seeder

## Architecture
- **Faker** for realistic data (already a dev dep)
- **SQLAlchemy Core `insert().values(batch)`** for bulk inserts
- **FK ID pool** with Pareto distribution (80/20 rule)
- **Rich progress bar** with ETA and resumable seeding
- **Typer CLI** `hyperadmin seed --count N --batch-size 5000 --database-url URL`

## Seeding order
Accounts → Contacts → Invoices → InvoiceItems → Bills → BillItems → JournalEntries → JournalLines → Auth tables
