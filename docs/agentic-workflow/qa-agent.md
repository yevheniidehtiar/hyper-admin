# Agent 5: QA Agent

| Property | Value |
|---|---|
| **Tier** | Utility (Tests) / Production (Analysis) |
| **Trigger** | PR passes code review |
| **Purpose** | Run comprehensive test suite including compatibility matrix |
| **Est. Cost** | 5k - 20k tokens for analysis per task |

## Testing Scope

| Test type | Tool | What it checks |
|---|---|---|
| Unit tests | CI (pytest) | Function-level correctness |
| Integration tests | Jules (in VM) | Module interaction, real I/O |
| Type checking | CI (mypy/pyright) | Type safety across public API |
| Compatibility matrix | GitHub Actions matrix | Python 3.10, 3.11, 3.12, 3.13 |
| Backward compat | Jules | Import old version, run against new — no breaks |
| Dependency audit | `pip-audit` | Known vulnerabilities in deps |
| Documentation build | CI | Docs compile without errors, examples run |

## Compatibility Matrix

```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12', '3.13']
    os: [ubuntu-latest, macos-latest]
```

## QA Report

After test execution, {{ default_ai_model }} analyses results:

```markdown
## QA report — #17 RetryPolicy implementation

**Test results**: 47 passed, 0 failed, 2 skipped
**Coverage**: 91% on new code (target: 80%) ✅
**Compatibility**: All matrix combinations green ✅
**Type check**: mypy strict — clean ✅
**Backward compat**: v0.x import test — passed ✅

**Risk assessment**: Low
**Recommendation**: Ready for release candidate

**Skipped tests rationale**:
- `test_retry_with_real_server`: Requires network (CI-skip expected)
- `test_retry_windows_specific`: Platform-specific, no Windows in matrix
```

## Failure Escalation

```
Tests fail
  → CI provides failure output
  → {{ default_ai_model }} analyses: code bug or test environment issue?
    → Code bug: Create sub-issue, route back to dev agent
    → Environment issue: Fix CI config, re-run
    → Flaky test: Label "flaky", investigate pattern across last 5 runs
  → If > 3 bugs per task: escalate to human (likely spec problem)
```
