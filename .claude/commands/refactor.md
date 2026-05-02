---
description: Deep structural refactoring guided by classic software engineering principles
argument-hint: "[file-or-glob-pattern]"
---

Analyze the structural quality of the specified files (or all changed files if no argument given). Audit naming, decomposition, abstraction depth, coupling, cohesion, public API compatibility, and legacy safety, then refactor guided by principles from Clean Code, Refactoring, A Philosophy of Software Design, SICP, Design Patterns, Working Effectively with Legacy Code, The Pragmatic Programmer, and Code Complete.

This skill focuses on design-level quality — not algorithmic performance (use `/optimize` for that).

---

## Step 1 — Identify Target Code

If `$ARGUMENTS` is provided, use it as a file path or glob pattern.

Otherwise, detect changed files:

```bash
git diff --name-only HEAD~1 HEAD -- '*.py'
git diff --name-only -- '*.py'
```

If no files are found, ask the user what to review.

Additionally, read `CONSTITUTION.md` to ensure all refactoring respects the project's structural rules (module boundaries, dependency direction, naming conventions).

---

## Step 2 — Naming Audit

*Sources: Clean Code Ch. 2 (Meaningful Names), Code Complete Ch. 11 (Variable Names), Fowler's "Mysterious Name" smell*

For every identifier in the target files — variables, functions, classes, parameters, modules — check against these rules:

| Red Flag | Example | Fix |
|---|---|---|
| Single-letter variables outside comprehensions/lambdas | `d = get_data()` | Rename to reveal intent: `user_records = get_data()` |
| Generic names in non-trivial scope | `result = process(data)` | Name after what it contains: `validated_order = process(raw_order)` |
| Booleans without `is_`/`has_`/`can_`/`should_` prefix | `active = check(user)` | `is_active = check(user)` |
| Negated boolean names | `not_found`, `is_not_valid` | Flip: `found`, `is_valid` — avoids double negation in `if not not_found` |
| Abbreviations saving < 5 characters | `btn`, `msg`, `cfg` | Spell out: `button`, `message`, `config` |
| Vague function names without specificity | `process_data()`, `handle_request()` | Name the transformation: `validate_and_normalize_order()` |
| Inconsistent vocabulary for the same concept | Mix of `get`/`fetch`/`retrieve` or `remove`/`delete` | Pick one term per concept, use it everywhere |
| Type-encoded names | `user_list`, `name_string` | Drop the suffix unless distinguishing types in same scope |
| Name-behavior mismatch | `get_user()` returns a boolean | Rename to `user_exists()` or change the return type |
| Cross-module import of `_`-prefixed names | `from module import _helper` | Make public (drop `_`) or restructure to avoid cross-module private access |

**Do NOT:**
- Rename variables in code outside the target set
- Rename public API symbols re-exported from `__init__.py` without going through Step 6 (API Compatibility)
- Impose naming conventions that conflict with `CONSTITUTION.md`

---

## Step 3 — Function and Method Decomposition

*Sources: Clean Code Ch. 3 (Functions), Fowler's Extract Method catalog, SICP 1.1-1.3 (composition), Code Complete Ch. 7 (Routines)*

For every function and method in the target files, check:

| Red Flag | Detection Rule | Refactoring Move |
|---|---|---|
| Function > 30 LOC (excluding docstring) | Count non-blank, non-comment lines | **Extract Method** — pull cohesive blocks into named functions |
| More than 4 parameters (excluding `self`/`cls`) | Count params | **Introduce Parameter Object** (dataclass/TypedDict), or split function |
| Multiple responsibilities | `and` in description, or blank-line-separated blocks doing different things | **Extract Method** for each responsibility |
| Deep nesting > 3 levels | Count `if`/`for`/`try` nesting depth | Guard clauses (early return), extract inner blocks |
| Flag arguments | `def process(data, is_admin=False)` | Split into two functions: `process_for_admin()`, `process_for_user()` |
| Long conditional chains (4+ branches) | Count `if`/`elif` | Dict dispatch, strategy pattern, or `match` statement (Python 3.10+) |
| Same code block in 3+ places | Textual/semantic similarity | **Extract Method** into shared function (DRY) |
| Mixed abstraction levels | High-level orchestration mixed with low-level string parsing | Push low-level details into helpers so the main function reads as a summary |
| Output arguments | Function modifies a mutable argument: `def fill(report_dict)` | Return a new value instead; caller assigns |

**Do NOT:**
- Split a naturally cohesive function just because it exceeds 30 LOC (e.g., a `match` with many 2-line cases)
- Extract one-liner helpers for code used in exactly one place
- Create wrapper functions with more arguments than the original

---

## Step 4 — Module Depth, Abstraction Barriers, and Information Hiding

*Sources: A Philosophy of Software Design Ch. 4-5 (deep vs. shallow modules, information leakage), SICP Ch. 2.1-2.2 (abstraction barriers), Pragmatic Programmer (orthogonality), Code Complete Ch. 5-6 (information hiding)*

| Red Flag | Detection Rule | Refactoring Move |
|---|---|---|
| Shallow class: interface as complex as implementation | Class with 5+ methods of 1-3 lines each, adding ceremony but no real abstraction | Merge into a simpler function or inline into caller |
| Pass-through methods | `def foo(self, x): return self.other.foo(x)` — pure delegation, no transformation | **Remove Middle Man** (Fowler) |
| Leaking implementation types | Returning raw SQLAlchemy `Row` or ORM internals from an adapter | Return domain objects or typed dicts |
| Law of Demeter violations | Chained access through internals: `view.adapter.engine.connect()` | Expose needed behavior via the immediate object's interface |
| Configuration explosion | Constructor with 8+ params, most defaulting to `None` | Builder pattern, or split into focused config objects per concern |
| Temporal coupling | `init()` then `configure()` then `start()` with no enforcement | Combine into one entry point, or use a state machine |
| God class | > 300 LOC or > 10 public methods spanning multiple concerns | **Extract Class** — split by responsibility into collaborating classes |
| Speculative base class | ABC with a single concrete subclass and no planned second | Inline the base class — avoid speculative generality |

**Do NOT:**
- Introduce deep modules where the project's adapter pattern is intentionally shallow for discoverability
- Add abstraction layers "for the future"
- Merge modules that `CONSTITUTION.md` keeps separate (views must not contain business logic, core must not import from views)
- Flag the project's adapter ABCs as "single implementor" — they have multiple implementations

---

## Step 5 — Coupling, Cohesion, and Dependency Hygiene

*Sources: GoF (composition over inheritance, program to interfaces), Pragmatic Programmer (DRY, orthogonality), Clean Code Ch. 10 (Classes)*

| Red Flag | Detection Rule | Refactoring Move |
|---|---|---|
| Circular imports | `TYPE_CHECKING` workarounds or bottom-of-file imports to break cycles | Extract shared types into a separate module, or invert dependency via Protocol |
| Feature envy | Method accesses another object's fields more than its own | **Move Method** to the class whose data it uses |
| Shotgun surgery | Changing one concept requires editing 5+ files | Consolidate related code, or define a shared abstraction |
| Duplicated business rules | Same rule encoded in two places (semantic duplication) | Extract into single source of truth |
| Inheritance for code reuse, not polymorphism | Subclass overrides 0 methods, or overrides most methods | Replace inheritance with composition: inject a collaborator |
| Gratuitous patterns | Strategy/Factory/Observer with only one variant | **Inline** — remove the pattern, use a direct call |
| Data clumps | Same group of 3+ parameters passed together across multiple functions | **Introduce Parameter Object** (dataclass/NamedTuple) |
| God import | Module imports from 10+ other project modules | Module likely has too many responsibilities — **Extract Class/Module** |
| Dependency direction violation | `core/` importing from `views/` or `adapters/` | Move the imported symbol to `core/` or use a Protocol |

**Do NOT:**
- Apply GoF patterns "just because" — a pattern must reduce complexity, not add ceremony
- Force DRY on code that is similar by coincidence but serves different domains (accidental duplication is fine)
- Refactor stable, well-tested code outside the target set
- Break the project's existing adapter pattern (it uses ABC inheritance for polymorphism by design)

---

## Step 6 — Public API Backward Compatibility

*Sources: Semantic Versioning, Hyrum's Law, Pragmatic Programmer (reversibility), Fowler's "Published Interface" concept*

HyperAdmin is an open-source library consumed by many projects. Every public symbol is a contract. This step gates all refactoring moves from Steps 2-5 through a compatibility check **before anything is applied**.

### What counts as public API

- Everything re-exported from `__init__.py` (top-level and per-subpackage)
- Class names, method signatures, and their parameter names/types/defaults
- Exception classes and their hierarchy
- Type aliases and Protocol definitions in `core/`
- Template block names and context variables (for projects extending templates)

### Breaking change detection

| Breaking Change | Detection Rule | Required Action |
|---|---|---|
| Renamed public function/class/method | Name differs from what `__init__.py` exported before | Keep old name as deprecated alias: `old_name = new_name` with `warnings.warn()` |
| Changed function signature (removed/reordered params) | Param list differs from current published signature | Keep old params with defaults, add `*` to force keyword-only for new params |
| Changed return type | Return annotation or structural shape differs | Provide adapter/wrapper returning old shape, deprecate it |
| Removed public symbol | Symbol previously in `__init__.py` no longer present | Restore and deprecate; remove only in next major version |
| Changed exception type raised | Different exception class on same code path | Subclass new exception from old, or catch-and-reraise during deprecation period |
| Changed default parameter value | Default changed, altering existing caller behavior | Preserve old default; add new parameter for new behavior |
| Renamed module file | `from hyperadmin.old_module import X` breaks | Add re-export shim in old module path with deprecation warning |

### Process for each refactoring move

1. Check if the affected symbol is public (exported from `__init__.py` or documented)
2. If public: apply the refactoring internally but preserve the old API surface with a deprecation path
3. Add `warnings.warn("X is deprecated, use Y instead", DeprecationWarning, stacklevel=2)` to old aliases
4. Document the deprecation in the summary report with target removal version

**Do NOT:**
- Silently rename or remove any public symbol without a deprecation shim
- Assume internal usage patterns — downstream projects may depend on any exported name
- Add deprecation warnings to private (`_`-prefixed) symbols — those are fair game to change freely
- Over-deprecate: if a refactoring only changes internals and the public interface is untouched, no shim is needed

---

## Step 7 — Legacy Code Safety Net

*Sources: Working Effectively with Legacy Code (Feathers) — cover-and-modify, seams, characterization tests; Refactoring Ch. 4 (building tests)*

Before applying any refactoring, ensure the code is safe to change:

### 7a. Check coverage

Run `pytest --cov=<target-module> --cov-report=term-missing` or check the existing coverage report. Identify lines and branches with no test coverage in the target files.

### 7b. Characterization tests

For uncovered code blocks that will be refactored, write characterization tests **before** changing the code. A characterization test captures current behavior (even if buggy) so refactoring does not accidentally change semantics.

### 7c. Identify seams and fixtures

For each function to refactor, identify where test doubles can be injected using **pytest-native patterns**:
- **Object seams**: method overrides via subclass or `pytest.MonkeyPatch` / `mocker.patch` (pytest-mock)
- **Link seams**: module-level imports patched with `mocker.patch("module.symbol")`
- **Preprocessing seams**: feature flags or environment variables via `monkeypatch.setenv()`

**Fixture DRY rules:**
- Fixtures must be atomic, focused, and reusable — one fixture per concern
- If a fixture (or mock) is used in **2+ test files**, move it to `conftest.py`
- Never duplicate the same fixture across test files; import from `conftest.py` instead
- To create a variant, copy the shared fixture and adjust only the differing attributes — do not rebuild from scratch

### 7d. Preserve public contracts

Verify that all `__init__.py` exports maintain their signatures and return types (validated in Step 6).

**Do NOT:**
- Write tests for code you are not refactoring
- Write characterization tests for trivially simple code (< 5 LOC, no branching)
- Skip this step — refactoring without tests is "edit and pray" (Feathers)

---

## Step 8 — Apply Fixes

For each finding from Steps 2-7:

1. **State the issue**: which smell, which book principle it violates, and the structural cost (readability, change amplification, cognitive load)
2. **Name the refactoring move**: use Fowler's catalog name where applicable (Extract Method, Move Method, Introduce Parameter Object, Remove Middle Man, etc.)
3. **Apply the fix directly** — do not just suggest it
4. If the symbol is public API (per Step 6), include the deprecation shim
5. If a characterization test was added in Step 7, re-run it to verify behavior is preserved

After applying all fixes, run:

```bash
just lint
just test
```

Fix any regressions before proceeding. If `just lint` introduces formatting changes, accept them. If `just test` reveals a broken test, revert the specific refactoring that caused it and note it in the report.

---

## Step 9 — Summary Report

Print two tables:

### Refactoring table

```
| File:Line | Function/Class | Smell | Book Principle | Refactoring Applied |
|-----------|----------------|-------|----------------|---------------------|
| views/dynamic.py:158 | list_view | Function > 30 LOC, mixed abstraction | Clean Code Ch.3, APoSD Ch.4 | Extract Method: _build_pagination(), _build_row_dicts() |
| core/model.py:74 | ModelAdmin | Shallow class, no behavior | APoSD Ch.4 | Inlined into registry caller |
| routing.py:42 | create_admin_router | 11 parameters | Clean Code Ch.3 | Introduced RouterConfig dataclass |
```

### API compatibility table (only if public symbols were affected)

```
| Old Symbol | New Symbol | Deprecation Shim | Target Removal Version |
|------------|------------|------------------|------------------------|
| ModelAdmin.get_list | ModelAdmin.build_list_context | old name aliased with DeprecationWarning | 1.0.0 |
```

If no public API was affected, print: `No public API changes — backward compatibility preserved.`

If no structural issues were found at all, print: `All reviewed code meets structural quality standards.`
