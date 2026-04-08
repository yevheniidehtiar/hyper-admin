# Parallel Planning Universes (PPU) Analysis Report

**Experiment:** Three autonomous AI agents independently re-plan the v0.4.0 Responsive Design epic
**Base commit:** `a548c8b` (develop)
**Branches:** `experiment/ppu-alpha`, `experiment/ppu-beta`, `experiment/ppu-gamma`
**Date of analysis:** 2026-04-08

---

## Layer 1: Raw Git Diff

### Branch vs Base

| Comparison | Responsive files changed | Key operations |
|---|---|---|
| **Alpha vs base** | 12 files | 1 epic.md created, 9 stories moved into epic dir, 2 stories modified (priority, deps) |
| **Beta vs base** | 12 files | 1 new epic.md, 5 new stories created, 7 existing stories modified (deps, labels, epic_ref), 1 story marked superseded |
| **Gamma vs base** | 18 files | 1 new epic.md, 10 new stories created, 7 existing stories moved+modified, 1 story removed in iter 5 |

### Cross-branch Divergence

| Comparison | Summary |
|---|---|
| **Alpha vs Beta** | Different epic directory names (`epic-responsive-design` vs `epic-responsive-design-v040`). Beta split #452 into 3 new stories; Alpha kept #452 monolithic. Beta created 3 new testing stories; Alpha has none. |
| **Alpha vs Gamma** | Same epic directory name, but Gamma has 17 stories vs Alpha's 11. Gamma added 10 new a11y/UX stories; Alpha added 0 new stories. Gamma upsized sidebar (#458) from M to L and E2E from L to L (unchanged). |
| **Beta vs Gamma** | Maximum divergence. Different epic dir names. Beta has 11 stories, Gamma has 17. Beta focuses on parallelism/splitting; Gamma focuses on a11y coverage. Beta's dependency graph is flatter; Gamma's is deeper. |

---

## Layer 2: Structural Comparison Table

| Metric | Base | Alpha | Beta | Gamma |
|---|---|---|---|---|
| **Story count (responsive epic)** | 11 (scattered, no epic dir) | 11 | 11 (5 new + 6 in stories/) | 17 |
| **Scenario count (BDD, responsive)** | 38 | 39 | 43 | 68 |
| **Epic directory exists?** | No | Yes (`epic-responsive-design/`) | Yes (`epic-responsive-design-v040/`) | Yes (`epic-responsive-design/`) |
| **Max dependency chain depth** | 4 (#447->#452->#461->#464) | 4 (#447->#452->#461->#464->#470) | 4 (C1-A->C1-B->C2-A->C3-A) | 5 (#447->#452->#458->#465->#470->E2E) |
| **Max parallel width** | 3 (#458, #461, #467 after #452) | 3 (#458, #461, #467 after #452) | 3 (entire Cycle design: 3 agents) | 7 (#461, #458, #467, iOS, skip, touch, page-header after #452) |
| **size:S count** | 4 | 4 | 6 | 6 |
| **size:M count** | 5 | 5 | 5 | 8 |
| **size:L count** | 2 | 2 | 0 | 3 |
| **New stories (not in base)** | -- | 0 (epic.md only) | 5 (W1-A tokens, W1-B layout, E2E suite, visual reg, demo showcase) | 10 (iOS zoom, skip-to-content, touch feedback, page header, scroll-to-top, typography, skeleton, empty states, orientation, new E2E) |
| **Removed stories** | -- | 0 | 0 (1 superseded) | 1 (CSS transitions, removed in iter 5) |
| **Stories with a11y-focused BDD scenarios** | 1 (navbar has SR scenario) | 1 (same as base) | 0 | 7 (sidebar focus trap, skeleton SR, empty state SR, table SR, login SR, navbar SR, skip-to-content) |

### Key Observations

- **Alpha** is essentially the base plan reorganized into an epic directory with minimal content changes.
- **Beta** eliminated all size:L stories by splitting #452 into S+M+M parts, achieving the flattest dependency graph.
- **Gamma** nearly doubled the scenario count and added 10 new stories, all accessibility or UX-polish focused.

---

## Layer 3: Dependency Graph Visualization

### Branch Alpha

```
Wave 1: [#447 (done)]
Wave 2: [#452 CSS foundation (L)]
Wave 3: [#458 sidebar (M), #461 table (M), #467 forms (M)]   -- 3 parallel
Wave 4: [#464 pagination (M), #465 navbar (S)]                -- 2 parallel
         #463 dashboard (M, deferrable, external dep #462)
Wave 5: [#470 login/detail/dashboard (S)]
Wave 6: [#471 E2E tests (L)]
         #472 docs (S, deferrable)

Critical path length: 6 waves
Max parallelism: 3
Time to first demoable state: Wave 3 (table cards visible after #452 completes)
```

### Branch Beta

```
Cycle 1 (3 agents, true parallel, no deps):
  [C1-A tokens (S), C1-B layout (M), C1-C table (M)]

Cycle 2 (3 agents + stagger):
  [C2-A sidebar (M), C2-B forms (M), C2-C pagination (M)]
  Stagger pickup: C2-D login/detail (S) when C2-C finishes

Cycle 3 (3 agents + stagger):
  [C3-A navbar (S), C3-B E2E tests (M), C3-C demo showcase (S)]
  Stagger pickup: C3-D visual regression (S) when C3-A finishes

Critical path length: 3 cycles
Max parallelism: 3 (strict slot allocation)
Time to first demoable state: End of Cycle 1 (table card layout -- C1-C is independent)
```

### Branch Gamma

```
Wave 1: [#452 CSS foundation (L)]
Wave 2: [#458 sidebar (L), #461 table (M), #467 forms (M),
          iOS zoom (S), skip-to-content (S), touch feedback (S),
          page header (M), scroll-to-top (S), typography (S)]   -- 9 parallel!
Wave 3: [#464 pagination (M), #465 navbar (M),
          orientation (S, stretch), skeleton (M), empty states (M, stretch)]
Wave 4: [#470 login/detail/dashboard (M)]
Wave 5: [E2E test suite (L)]

Critical path length: 5 waves
Max parallelism: 9 (theoretical, Wave 2)
Time to first demoable state: Wave 2 (many small improvements visible immediately after #452)
```

### Comparison

| Metric | Alpha | Beta | Gamma |
|---|---|---|---|
| Critical path (waves/cycles) | 6 | 3 | 5 |
| Max parallelism | 3 | 3 | 9 (theoretical) |
| First demoable state | Wave 3 | Cycle 1 | Wave 2 |
| Practical agent slots used | 1-3 | 3 (consistent) | 1-9 (variable) |

Beta achieves the shortest wall-clock time by (a) splitting #452 to unblock Cycle 1 parallelism, (b) making C1-C (table) independent via self-contained media queries, and (c) using stagger pickups to keep all 3 agent slots busy.

---

## Layer 4: Semantic Narrative Diff

### Alpha: The Conservative Consolidator

**Thesis:** The base plan was structurally sound but organizationally scattered. The primary intervention needed was structural: create a proper epic directory, move all stories under it, fix epic_ref pointers, validate the dependency graph, and confirm BDD coverage.

**Key structural decisions:** Alpha created the epic directory and moved all 10 existing stories into it. It promoted #452 to `priority: high`, demoted #472 (docs) and #463 (dashboard) to `priority: low` / deferrable, and updated #472's blocked_by to reference both #452 and #470. It added one BDD scenario to #463 (widget grid mobile stacking). The dependency graph was left almost identical to the base, with the correction that #452 is unblocked (its dependency #447 is already done).

**Blind spots:** Alpha made zero changes to the actual scope of individual stories. No accessibility scenarios were added. No attempt was made to split the size:L stories (#452, #471) which are the biggest risk items. Alpha treated the plan as "already correct, just disorganized," which is a generous reading of the base plan that misses real gaps in a11y and UX polish coverage.

**Surprising choices:** Iterations 3 and 4 produced zero file changes -- Alpha concluded the BDD audit "passed" and scope was already right. This is surprisingly passive. The iteration 5 change was only updating the epic status to `in_progress` and a timestamp. Alpha converged fastest but also changed the least.

---

### Beta: The Parallelism Engineer

**Thesis:** Wall-clock delivery time is the binding constraint. The plan should be restructured to maximize the number of stories that can execute simultaneously in 3-agent cycles, with zero file conflicts between concurrent stories. The size:L bottleneck (#452) must be split.

**Key structural decisions:** Beta's most impactful move was splitting #452 into three parts: W1-A (breakpoint tokens, S, touches only `_tokens.css`), W1-B (mobile-first layout rewrite, M, touches `_responsive.css`, `_layout.css`, `_sidebar.css`, `_fieldsets.css`), and making C1-C (data table, M) fully independent with self-contained media queries in `_table.css`. This eliminated all dependencies in Cycle 1, allowing 3 agents to run truly in parallel from day one. Beta also created a file-target map to prove zero overlap between concurrent stories. The "stagger pickup" concept (freed agent from fast-finishing story picks up a queued story) was novel.

Beta added three new testing stories: visual regression baseline, E2E responsive test suite (downsized from L to M by narrowing scope), and a demo app showcase. Beta also flattened the dependency from #461->#464 (table->pagination was originally chained in base; Beta made pagination depend on W1-B instead). The login/detail story (#470) was reduced from 5 blockers to 1 (only W1-B needed).

**Blind spots:** Zero accessibility work. No new a11y scenarios anywhere. No stories for iOS zoom, focus trapping, screen reader support, or skip-to-content. Beta's plan would ship a responsive layout that passes no WCAG checks. This is a significant gap for a public-facing admin framework. Also, Beta left #447, #472, and #471 in their original (wrong) epic directory -- it only moved the stories it actively modified.

**Surprising choices:** Marking #452 as "superseded" with a pointer to the replacement stories is good migration hygiene. The `@layer responsive` specificity strategy and the explicit "shared file strategy" section in the epic are production-aware. The agent tier assignment (Sonnet for CSS, Opus for E2E) shows thoughtful resource allocation. Demo checkpoints on every story is a nice quality gate.

---

### Gamma: The Accessibility Advocate

**Thesis:** Responsive design without accessibility is half a feature. Every mobile interaction must work for screen readers, keyboard navigation, and users with motor impairments. The plan should add dedicated stories for each a11y concern and ensure every existing story has a11y-flavored BDD scenarios.

**Key structural decisions:** Gamma added 10 entirely new stories, most of which the other agents never considered: iOS input zoom prevention (font-size >= 16px), skip-to-content link enhancement, CSS-only touch feedback (:active states), responsive page header/action bar, mobile scroll-to-top after HTMX navigation, HTMX loading skeleton states, mobile empty state designs, mobile typography polish, and orientation handling. The sidebar story (#458) was upsized from M to L with 7 scenarios (up from 5 in base) because Gamma added focus trapping and `role="dialog"` with aria-label requirements. The E2E test suite was also sized at L with 11 comprehensive scenarios covering a11y.

Gamma added `prefers-reduced-motion` respect to 3 stories (transitions, skeleton, scroll-to-top). The epic principles explicitly mandate WCAG 2.1 AA, 44px touch targets, and screen reader support.

**Blind spots:** Gamma never split #452 -- it remains a size:L monolith that is the sole bottleneck for 9 downstream stories. With 17 stories and a deep dependency chain (5 waves), the wall-clock time is significantly longer than Beta's 3-cycle plan. Gamma's theoretical max parallelism of 9 is unrealistic unless you have 9 agent slots. The scope expansion (17 stories vs base's 11) risks milestone overrun. Gamma acknowledged this by marking 2 stories as "stretch," but 17 stories is still ambitious.

**Surprising choices:** Removing the CSS transitions story in iteration 5 was smart scope control -- it recognized that sidebar #458 already includes slide transitions and `_accessibility.css` handles `prefers-reduced-motion` globally, making a separate story redundant. The "demo-app-first" principle (every story must be verifiable in examples/) is a practical quality gate that neither Alpha nor Beta included in their epic principles. Promoting `#470` from HIGH to MEDIUM was unexpected but defensible -- it is polish, not infrastructure.

---

### Synthesis

#### Convergence Points (All Three Agree)

1. **A dedicated epic directory is needed.** All three created one (Alpha and Gamma: `epic-responsive-design/`, Beta: `epic-responsive-design-v040/`). The base state -- stories scattered across `.meta/stories/` and misattributed to the auth epic -- was universally recognized as broken.

2. **#452 is the critical foundation.** All three treat #452 (or its replacement) as the Wave 1 blocker. All three agree it must be done first.

3. **#472 (docs) and #463 (dashboard template) are deferrable.** Alpha and Beta explicitly lower their priority. Gamma excludes them entirely from its epic. Nobody considers them must-ship for v0.4.0.

4. **The sidebar (#458), table (#461), and forms (#467) are the core Wave 2 parallel tranche.** All three branches have these three running concurrently after the CSS foundation completes.

5. **#470 (login/detail/dashboard views) is final polish before E2E tests.** All three place it late in the dependency chain.

6. **E2E tests are the terminal story.** All three have E2E tests blocked by all feature stories.

#### Divergence Points (Genuine Design Tensions)

1. **Split vs. keep #452 (size:L).** Beta splits it into 3 stories for parallelism; Alpha and Gamma keep it monolithic. This is the single highest-impact structural decision. Beta's split enables Cycle 1 true parallelism but adds coordination complexity. Gamma's approach is simpler but creates a longer critical path.

2. **Scope: 11 stories vs 17 stories.** Alpha/Beta keep roughly the original scope. Gamma nearly doubles it. The tension is real: are the 10 new Gamma stories "gold-plating" or "necessary accessibility work"? The iOS zoom fix (S) and skip-to-content (S) are arguably must-have for any admin framework; HTMX skeleton states and empty state designs are nice-to-have.

3. **Accessibility: explicit stories vs. implicit.** Beta has zero a11y work; Alpha has 1 scenario. Gamma has 7 stories with dedicated a11y scenarios and a WCAG 2.1 AA mandate in the epic principles. This maps to a real product decision about v0.4.0's ambition level.

4. **#461 (table) dependency on #452.** Beta makes the table story independent (self-contained media queries in `_table.css`); Alpha and Gamma chain it after #452. Beta's approach is valid CSS architecture but means the table story cannot use breakpoint tokens from `_tokens.css`.

5. **#470 blocker count.** Alpha: 5 blockers. Beta: 1 blocker (W1-B only). Gamma: 5 blockers. Beta's aggressive blocker reduction lets #470 start in Cycle 2 instead of Wave 5, but risks quality if the story ships before sidebar and navbar are ready.

#### Best Ideas from Each

**From Alpha:**
- Clean epic directory consolidation with proper `epic_ref` pointer updates
- Conservative stability: no over-engineering, recognizes what is already correct
- Explicit scope tiers: "8 must-ship + 2 deferrable" with labels

**From Beta:**
- Split #452 into S+M stories to unblock Cycle 1 parallelism (best single structural decision)
- File-target map proving zero conflict between concurrent stories
- Stagger pickup concept for keeping agent slots busy
- Demo checkpoints on every story
- Agent tier assignment (Sonnet for CSS/template, Opus for E2E)
- Self-contained media query strategy eliminating `_responsive.css` as shared bottleneck
- Visual regression baseline story (lightweight guard against desktop regression)

**From Gamma:**
- iOS input zoom prevention (size:S, high value, missed by both others)
- Skip-to-content and ARIA landmark enhancements (size:S, WCAG requirement)
- Focus trap and `role="dialog"` on sidebar overlay (a11y mandated)
- `prefers-reduced-motion` respect on all animated stories
- "Demo-app-first" principle in epic
- WCAG 2.1 AA as explicit epic constraint
- Removal of CSS transitions story (smart scope cut)
- Page header/action bar responsive story (catches a real overflow bug on 320px)
- Scroll-to-top after HTMX navigation (real UX pain point)

#### Recommended Synthesis: "Best of All Three"

The optimal plan takes Beta's structure, adds Gamma's top a11y stories, and uses Alpha's organizational discipline:

**Epic structure:** Beta's 3-cycle architecture with stagger pickups.

**Story count:** 14 stories (Beta's 11 + 3 cherry-picked from Gamma).

Cherry-pick from Gamma:
1. **iOS input zoom prevention** (S) -- add to Cycle 2 stagger slot
2. **Skip-to-content and landmark enhancements** (S) -- add to Cycle 2 stagger slot
3. **Responsive page header and action bar** (M) -- add to Cycle 2 slot C (replace pagination which becomes C2-D stagger)

Do NOT cherry-pick: HTMX skeleton states, empty states, orientation handling, scroll-to-top, CSS touch feedback, typography polish. These are post-v0.4.0 polish (v0.4.1).

**Mandatory additions to existing stories (from Gamma):**
- Add focus trap + `role="dialog"` scenarios to sidebar story
- Add `prefers-reduced-motion` scenario to sidebar story
- Add screen reader scenario to login/detail story
- Add `font-size >= 16px` acceptance criterion to forms story
- Add WCAG 2.1 AA as explicit epic principle

**Dependency graph:**
```
Cycle 1 (3 agents, true parallel):
  C1-A: Breakpoint tokens (S)
  C1-B: Mobile-first base layout (M)
  C1-C: Responsive data table (M, self-contained)

Cycle 2 (3 agents + 2 stagger pickups):
  C2-A: Sidebar + focus trap + SR dialog (M)
  C2-B: Touch-friendly forms (M)
  C2-C: Page header + action bar (M)
  C2-D stagger: Pagination/filter (M)
  C2-E stagger: iOS zoom prevention (S)
  C2-F stagger: Skip-to-content (S)

Cycle 3 (3 agents + stagger):
  C3-A: Navbar responsive (S)
  C3-B: Login/detail/dashboard views (S)
  C3-C: E2E responsive tests (M)
  C3-D stagger: Visual regression baseline (S)

Total: 14 stories across 3 cycles
```

---

## Layer 5: Commit History Analysis

### Alpha (5 iterations)

```
5a2dc92 iter 5 — final review, mark epic in_progress, update timestamp     [1 file]
a80e47b iter 4 — scope trim validated, no changes needed                    [0 files]
ddf3e3f iter 3 — BDD scenario audit passed, no changes needed               [0 files]
94ae2ae iter 2 — validate dependency graph, mark #452 as unblocked          [1 file]
3f21e9d iter 1 — consolidate responsive stories under epic-responsive-design [12 files]
```

**Pattern: Fast convergence.** Alpha did all substantive work in iteration 1 (12 files). Iterations 2-4 were validation passes that found nothing to fix. Iteration 5 was a cosmetic status update. This signals that Alpha treated the base plan as essentially correct and converged immediately after reorganizing it. No oscillation detected.

### Beta (5 iterations)

```
3f28160 iter 5 — wall-clock optimization, first-demo marker, agent tiers     [1 file]
af39b7f iter 4 — wave planning, reduce 4 waves to 3 cycles with stagger     [6 files]
a40f086 iter 3 — agent sizing audit, add demo checkpoints                    [0 files]
bef1d95 iter 2 — parallelism audit, file target map, promote table to W1     [6 files]
3d3c439 iter 1 — dependency graph surgery, split #452, create epic           [4 files]
```

**Pattern: Steady refinement.** Beta made structural changes in iterations 1, 2, and 4. Iteration 1 was the big split. Iteration 2 promoted the table to Wave 1 (key parallelism insight). Iteration 4 compressed 4 waves to 3 cycles with the stagger concept (the most impactful late-iteration idea). Iteration 5 was cosmetic polishing. No oscillation -- each iteration built on the previous. The big idea (stagger) came in iteration 4, suggesting Beta was still discovering optimizations but within a settled framework.

### Gamma (5 iterations)

```
2888a45 iter 5 — scope control: remove CSS transitions story, finalize 17    [5 files]
d0c7774 iter 4 — polish stories, fix BDD size labels, expand E2E scenarios   [5 files]
7625d37 iter 3 — add missing stories: responsive page header, scroll-to-top  [3 files]
e8e634e iter 2 — UX-impact priority reorder, promote touch feedback          [3 files]
4265ca6 iter 1 — accessibility audit, move stories to epic dir, add a11y     [17 files]
```

**Pattern: Expansion then contraction.** Gamma expanded scope in iterations 1-3 (added stories each time, peaking at 18 stories in iteration 4) and then contracted in iteration 5 by removing the CSS transitions story. This is a healthy arc: explore possibilities, then trim. However, iteration 5 still made substantive changes (5 files), suggesting Gamma had not fully stabilized. The scope reduction (18->17) was minor; a more aggressive cut would have brought it closer to Alpha/Beta's 11.

**Did any agent undo prior work?** Gamma removed one story in iteration 5 that it had created, which counts as mild oscillation. Alpha and Beta showed no reversals.

**Did later iterations make smaller changes?** Alpha: yes (12, 1, 0, 0, 1). Beta: partially (4, 6, 0, 6, 1 -- iteration 4 had a second peak). Gamma: roughly decreasing (17, 3, 3, 5, 5 -- but the tail is flat, not converging to zero).

**Did iteration 5 still produce major changes?** Alpha: no. Beta: no. Gamma: moderate (5 files, including a story deletion). Gamma was still exploring at iteration 5, while Alpha and Beta had settled.

---

## Recommended Next Steps

1. **Cherry-pick Beta's #452 split** (W1-A tokens + W1-B layout + self-contained C1-C table) into the actual v0.4.0 plan on develop. This is the single highest-value structural change and the only decision that materially reduces delivery time.

2. **Add Gamma's top 3 a11y stories** to the plan as size:S additions: iOS input zoom prevention, skip-to-content landmarks, and focus trap / SR dialog requirements folded into the sidebar story. These are WCAG 2.1 AA requirements that cost very little effort but significantly improve the quality bar.

3. **Adopt Beta's "file-target map" and "demo checkpoint" conventions** as epic-level documentation standards. Proving zero file conflict between concurrent stories prevents merge conflicts in multi-agent execution. Demo checkpoints on each story provide a natural acceptance gate.

4. **Add `prefers-reduced-motion` as a cross-cutting requirement** to the CSS foundation story and the epic principles (from Gamma), rather than as separate stories. This is a one-line CSS addition per animation but must be called out explicitly so agents do not forget it.

5. **Defer Gamma's remaining 7 new stories** (HTMX skeleton, empty states, orientation, scroll-to-top, touch feedback, typography polish, mobile empty state designs) to a v0.4.1 polish milestone. They are valuable but not must-ship for the initial responsive release.
