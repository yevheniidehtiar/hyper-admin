# OSS Triage Auditor (Optional)

> **Standalone agent** — not part of the core 8-agent workflow.
> Use when onboarding a new project, performing periodic backlog hygiene,
> or cleaning up after a spam wave.

| Property | Value |
|---|---|
| **Tier** | Production Model (Claude Sonnet) |
| **Trigger** | Manual — `/oss-triage-audit [dry-run\|live]` |
| **Purpose** | Full audit of issues, PRs, milestones: detect spam, enforce lifecycle, clean duplicates |
| **Est. Cost** | 10k–50k tokens per audit (scales with open issue count) |

## Inspiration

This agent is inspired by discussions between Python core maintainers and OSS project leads
at PyCon about the growing problem of AI-generated spam in open-source projects:

🎥 **[PyCon Talk — AI Spam in Open Source](https://www.youtube.com/watch?v=7WkGWQ1jIAU)**

Key takeaways that shaped this agent's design:

| Concept | Source Idea | How We Apply It |
|---------|------------|-----------------|
| **"Too-Long" Description Filter** | Flag PRs where description-to-code ratio is absurdly high (10k words for 5 lines) | Score signal: description-to-code ratio > 20:1 adds +25 to suspicion score |
| **Federated Reputation** | Contributors earn reputation through quality; burning it on spam PRs is costly | Score signal: zero prior merged PRs in the repo adds +10 to suspicion |
| **Constructive Friction / TTL** | Add minor blockers that break bot loops; auto-close if no human responds in time | TTL enforcement: `needs-human` + 14 days → auto-close; stale `idea` + 30 days → auto-close |
| **Mandatory Explainability** | If a submitter cannot explain the code, reject immediately | Score signal: no conversation/comments from author adds +10; bulk submissions add +10 |
| **Review the Spec, Not the Slop** | Prefer well-scoped plans over bulk-generated code dumps | Score signal: generic boilerplate without specific file/function references adds +20 |

## Audit Flow

```
┌──────────────┐
│  Fetch Data  │  ← gh issue list, gh pr list, gh api milestones
└──────┬───────┘
       ▼
┌──────────────┐
│ Score Items  │  ← AI-slop heuristic + ego-PR heuristic
└──────┬───────┘
       ▼
┌──────────────┐
│  Detect      │  ← Jaccard similarity on titles + body comparison
│  Duplicates  │
└──────┬───────┘
       ▼
┌──────────────┐
│  Enforce     │  ← Verify state labels, infer missing, fix conflicts
│  Lifecycle   │
└──────┬───────┘
       ▼
┌──────────────┐
│  Apply TTL   │  ← Close stale items past time-to-live thresholds
└──────┬───────┘
       ▼
┌──────────────┐
│  Generate    │  ← Structured markdown report with tables
│  Report      │
└──────────────┘
```

## Heuristic: Suspicious Content (AI-Slop)

Scoring system: 0–100. Threshold: **60** (flagged as `suspicious`).

| Signal | Weight | Detection |
|--------|--------|-----------|
| Description-to-code ratio > 20:1 | +25 | For PRs: body word count vs `additions + deletions`. For issues: body > 500 words with no code references |
| Generic boilerplate language | +20 | Patterns like "I noticed that", "This PR improves", "As a developer" without specific file/function names |
| PR not linked to any issue | +15 | Body lacks `#N`, `closes`, `fixes`, `resolves` patterns |
| Author has zero merged PRs in this repo | +10 | `gh pr list --author <login> --state merged` returns empty |
| LLM markers / excessive formatting | +10 | "As an AI", excessive markdown headers for simple changes, boilerplate structure |
| No conversation from author | +10 | Comments array empty or only bot comments |
| Bulk submissions (>3 open PRs from same author) | +10 | Group by author login, count open PRs |

## Heuristic: Ego-PR Detection

Scoring system: 0–100. Threshold: **50** (flagged as `suspicious`).

| Signal | Weight | Detection |
|--------|--------|-----------|
| Only whitespace/formatting changes | +30 | `additions + deletions < 10` AND files are non-functional (README, docs, comments only) |
| Typo-only fix | +25 | Diff contains only single-character or word changes in strings/comments |
| PR not linked to any issue | +20 | Same check as above |
| Title contains "typo", "minor fix", "cosmetic" | +15 | Case-insensitive string match on PR title |
| Changes don't touch `src/` | +10 | None of the changed file paths start with `src/` |

## Duplicate Detection

1. Normalize all issue titles: lowercase, strip punctuation, remove stop words
2. Compute Jaccard similarity on title token sets for each pair of open issues
3. If similarity > 0.6, OR if issues reference the same files and describe the same change → flag as duplicate
4. In `live` mode: close the newer issue with comment linking to the older one
5. In `dry-run` mode: report the pair for human review

## Lifecycle Enforcement

Verify each open issue has exactly **one** state label from the state machine:
`idea`, `researched`, `planned`, `approved`, `in-progress`, `review`, `qa-passed`, `released`.

| Condition | Action |
|-----------|--------|
| Zero state labels, has open PR | Apply `in-progress` |
| Zero state labels, has milestone | Apply `planned` |
| Zero state labels, freshly created | Apply `idea` |
| Multiple state labels | Keep most advanced, remove others |
| Missing size label on non-epic | Flag in report (no auto-fix) |

## TTL / Constructive Friction

| Condition | TTL | Action |
|-----------|-----|--------|
| `needs-human` label, no activity | 14 days | Auto-close with explanation |
| `idea` label, no activity | 30 days | Auto-close as stale idea |
| Open PR, no review activity | 21 days | Auto-close with reopen instructions |

All close messages include reopen instructions — nothing is permanently deleted.

## Integration with Label State Machine

This agent adds one new label that sits **outside** the normal lifecycle flow:

| Label | Color | Purpose |
|---|---|---|
| `suspicious` | `#D93F0B` | Flagged by triage audit — needs human review |

```
Any state ──(flagged)──► suspicious ──(human-reviewed)──► original state OR closed
```

The `suspicious` label is orthogonal: it can coexist with state labels or replace them
depending on the severity of the finding.

## Idempotency

- Before applying labels: check if `suspicious` is already present → skip
- Before posting comments: check for existing `<!-- oss-triage-audit -->` marker → skip
- All comments include `<!-- oss-triage-audit-<date> -->` HTML comment for dedup

## Human Checkpoints

- The agent **never permanently deletes** issues or PRs
- All closures are reversible (reopen)
- `suspicious` flags require human review before permanent rejection
- `dry-run` mode (default) produces a report with zero mutations
- `live` mode posts explanatory comments on every flagged item (mandatory explainability)

## Output Report

Structured markdown with these sections:

1. **Summary** — total counts (issues, PRs, flagged, duplicates, violations, closed)
2. **Suspicious Items** — number, title, author, score, top signals
3. **Ego-PRs** — number, title, author, score, top signals
4. **Potential Duplicates** — issue A, issue B, similarity score, recommendation
5. **Lifecycle Violations** — number, title, missing label, applied label
6. **Stale Items Closed** — number, title, last activity date, close reason
7. **Valid Issues (Sorted)** — number, title, state, size, age (prioritized by impact)
