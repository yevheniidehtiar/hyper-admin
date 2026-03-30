# Agent 8: Community Signal Ingestion

| Property | Value |
|---|---|
| **Tier** | Production Model (Triage) |
| **Trigger** | New issue, discussion, or PR from external contributor |
| **Purpose** | Triage community input and route to appropriate workflow |
| **Est. Cost** | 2k - 10k tokens per community interaction |

## Triage Flow

```
New community issue/discussion
  │
  ▼
Claude Sonnet classifies:
  │
  ├── Bug report → Validate reproduction steps → Create task in workload queue
  ├── Feature request → Feed to Deep Research agent for analysis
  ├── Question → Auto-respond with docs link or answer from project knowledge
  ├── Duplicate → Link to existing issue, close with explanation
  └── Spam/off-topic → Label for human review, don't auto-close
```

## Contributor Experience

When a community member submits a PR:

1. Auto-label with `community` tag
2. Code Review Agent reviews (same quality as internal PRs)
3. If changes requested: constructive review explaining *why* — critical for OSS community health
4. If PR addresses existing issue: auto-link them
5. On merge: add contributor to `CONTRIBUTORS.md`

## Escalation Path (Community vs Internal)

| Scenario | Internal PR | Community PR |
|---|---|---|
| Review fails | Re-dispatch to dev agent automatically | Post helpful review comment, wait for contributor |
| No update 14 days | N/A | Polite ping |
| No update 30 days | N/A | Close with "feel free to reopen" |
| Merged | Standard | Add to CONTRIBUTORS.md |
