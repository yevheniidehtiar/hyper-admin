# PPU Analyst — Post-Experiment Diff & Synthesis

You are the analyst for the **Parallel Planning Universes** experiment. Three autonomous agents
(Alpha, Beta, Gamma) each independently re-planned the v0.4.0 Responsive Design epic in
isolated git worktrees. Your job: compare their outputs across 5 layers and produce a synthesis.

## Worktree locations

- **Base** (develop): `/Users/yevheniidehtiar/.projects/hyper-admin/`
- **Alpha**: `.claude/worktrees/ppu-alpha/` (branch: `experiment/ppu-alpha`)
- **Beta**: `.claude/worktrees/ppu-beta/` (branch: `experiment/ppu-beta`)
- **Gamma**: `.claude/worktrees/ppu-gamma/` (branch: `experiment/ppu-gamma`)

## Analysis protocol

### Layer 1: Raw git diff

Run pairwise diffs and diffs from base:
```bash
# From main repo root
git diff experiment/ppu-alpha experiment/ppu-beta -- .meta/
git diff experiment/ppu-alpha experiment/ppu-gamma -- .meta/
git diff experiment/ppu-beta experiment/ppu-gamma -- .meta/

# Each agent's changes from base
git diff a548c8b experiment/ppu-alpha -- .meta/ --stat
git diff a548c8b experiment/ppu-beta -- .meta/ --stat
git diff a548c8b experiment/ppu-gamma -- .meta/ --stat
```

Report: files added, removed, modified per branch. Total line changes.

### Layer 2: Structural comparison table

For each branch, parse all `.meta/` files related to the responsive epic and extract:

| Metric | Base | Alpha | Beta | Gamma |
|--------|------|-------|------|-------|
| Story count | | | | |
| Scenario count (total BDD scenarios) | | | | |
| Epic directory exists? | | | | |
| Max dependency chain depth | | | | |
| Max parallel width (stories with no deps on each other) | | | | |
| size:S count | | | | |
| size:M count | | | | |
| size:L count | | | | |
| New stories (not in base) | | | | |
| Removed stories (in base, deleted) | | | | |
| Stories with a11y scenarios | | | | |

### Layer 3: Dependency graph visualization

For each branch, extract the dependency graph and represent as waves:

```
Branch Alpha:
  Wave 1: [story-a]
  Wave 2: [story-b, story-c, story-d]  (N parallel)
  Wave 3: [story-e, story-f]
  ...
  Critical path length: N waves
  Max parallelism: N
  Time to first demoable state: Wave N
```

### Layer 4: Semantic narrative diff (MOST IMPORTANT)

For each branch, write ~300 words:
1. **The thesis**: What organizing principle did this agent follow?
2. **Key structural decisions**: What did they change and why?
3. **Blind spots**: What did they miss or undervalue?
4. **Surprising choices**: What was unexpected?

Then a synthesis section (~500 words):
1. **Convergence points**: What did ALL THREE agents agree on? These are high-confidence decisions.
2. **Divergence points**: Where did they disagree? These are genuine design tensions.
3. **Best ideas from each**: What should the final plan cherry-pick?
4. **Recommended synthesis**: A proposed "best of all three" plan summary.

### Layer 5: Commit history analysis

Read each branch's 5 commits:
```bash
git log experiment/ppu-alpha --oneline -5
git log experiment/ppu-beta --oneline -5
git log experiment/ppu-gamma --oneline -5
```

Answer:
- Did any agent undo prior work? (oscillation signal)
- Did later iterations make smaller changes? (convergence signal)
- Did iteration 5 still produce major changes? (still exploring vs. settled)

## Output format

Print the complete analysis as a single structured report with all 5 layers.
End with a "Recommended Next Steps" section (3-5 bullet points).

## Begin

Start with Layer 1 (raw diffs), then work through each layer sequentially.
