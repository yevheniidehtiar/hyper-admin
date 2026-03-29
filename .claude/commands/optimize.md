---
description: Review changed code for algorithmic efficiency, readability, reusability, and memory usage
argument-hint: "[file-or-glob-pattern]"
---

Review code algorithms and use-case flows in the specified files (or all changed files if no argument given), then refactor for optimal performance.

---

## Step 1 — Identify Target Code

If `$ARGUMENTS` is provided, use it as a file path or glob pattern.

Otherwise, detect changed files:

```bash
git diff --name-only HEAD~1 HEAD -- '*.py'
git diff --name-only -- '*.py'
```

If no files are found, ask the user what to review.

---

## Step 2 — Algorithmic Complexity Audit

For every function and method in the target files, analyze:

### 2a. Time Complexity

Classify each function's worst-case time complexity. Flag anything above O(n) and determine if it can be reduced.

**Red flags to catch:**
- Nested loops over the same or correlated collections → O(n^2) or worse
- Repeated linear scans that could be replaced by a set/dict lookup
- Sorting where a single-pass approach (heap, partition, running min/max) suffices
- Quadratic string concatenation (use `"".join()` or `io.StringIO`)
- Calling `list.index()`, `x in list`, or `list.count()` inside a loop
- Re-computing values in a loop that could be hoisted or cached
- Recursive calls without memoization where overlapping subproblems exist
- Using `list.pop(0)` or `list.insert(0, ...)` — O(n) per call; suggest `collections.deque`

**Target:** O(n) or better. If O(n log n) is the theoretical minimum (e.g., sorting-dependent), accept it but note why.

### 2b. Space / Memory Complexity

Flag anything that allocates more memory than necessary:

- Building a full list when a generator/iterator would suffice (`list(x for x in ...)` → generator)
- Copying data structures unnecessarily (`.copy()`, slicing `[:]`, `list(dict.keys())`)
- Accumulating results in memory when they could be yielded or streamed
- Holding references that prevent garbage collection (circular refs, closures over large objects)
- Using dicts/lists for large N where `__slots__`, `namedtuple`, or `dataclass(slots=True)` would cut per-instance overhead
- Unbounded caches without `maxsize` — use `@functools.lru_cache(maxsize=N)` or `@functools.cache` only for bounded key spaces

**Target:** O(1) auxiliary space when possible; O(n) when output must be collected.

### 2c. Data Structure Selection

Verify the chosen data structure is optimal for the access pattern:

| Access pattern | Preferred structure |
|---|---|
| Membership test (`x in ...`) | `set` or `frozenset` |
| Key-value lookup | `dict` |
| Ordered unique keys with range queries | `sortedcontainers.SortedDict` |
| FIFO queue | `collections.deque` |
| Priority queue | `heapq` |
| Frequency counting | `collections.Counter` |
| Grouped iteration | `itertools.groupby` (pre-sorted) or `defaultdict(list)` |
| Fixed-schema records | `dataclass(slots=True)` or `NamedTuple` |

---

## Step 3 — Use-Case Flow Analysis

Trace each public entry point (view handler, API endpoint, CLI command, exported function) end-to-end:

1. **Identify hot paths** — code executed per-request or per-item in a batch
2. **Count I/O round-trips** — DB queries, HTTP calls, file reads inside loops (N+1 problem)
3. **Check early exits** — ensure guard clauses and short-circuits appear before heavy work
4. **Verify lazy evaluation** — expensive computations should be deferred until the result is actually needed
5. **Check batch operations** — replace per-item DB inserts/updates with bulk operations where possible

---

## Step 4 — Readability & Reusability Audit

### Readability
- Functions should do one thing; if a function has multiple concerns, split it
- Prefer descriptive variable names over comments explaining obscure names
- Replace magic numbers with named constants
- Complex conditionals should be extracted into well-named boolean variables or predicate functions
- Long method chains should be broken into named intermediate steps if meaning is unclear

### Reusability
- Repeated logic across 3+ call sites should be extracted into a shared function
- Functions should accept the narrowest possible input type (e.g., `Iterable` over `list`)
- Avoid hard-coded values that vary by call site — parameterize them
- Pure functions (no side effects) are preferred — they're easier to test, cache, and compose

### Do NOT
- Add abstractions for code used in only 1-2 places
- Add docstrings or type annotations to code you didn't change
- Refactor surrounding code that isn't part of the target

---

## Step 5 — Apply Fixes

For each finding:

1. State the issue: what it is, current complexity, why it matters
2. Show the fix with before/after complexity
3. Apply the fix directly — do not just suggest it

After applying all fixes, run:

```bash
poe lint
poe test
```

Fix any regressions before proceeding.

---

## Step 6 — Summary Report

Print a table summarizing what was changed:

```
| File:Line | Function | Before | After | Change |
|-----------|----------|--------|-------|--------|
| path:42   | process_items | O(n^2) time | O(n) time | replaced nested scan with dict lookup |
| path:88   | build_report  | O(n) space  | O(1) space | switched list accumulation to generator |
```

If no issues were found, print: `All reviewed code is already optimal.`
