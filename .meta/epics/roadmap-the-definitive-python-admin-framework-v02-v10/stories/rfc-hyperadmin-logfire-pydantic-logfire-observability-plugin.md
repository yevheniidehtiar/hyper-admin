---
type: story
id: PTGq0rtiWQH1
title: "RFC: hyperadmin-logfire — Pydantic Logfire observability plugin (first official plugin)"
status: todo
priority: medium
assignee: null
labels:
  - rfc
  - plugin
  - observability
estimate: null
epic_ref:
  id: 5RQIGVbDMSTJ
github:
  issue_number: 276
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b67ca37b1ef00c1ea2c909b914d2c47aab063fe69edd0971d47b86e3c0cdd41b
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T09:07:26Z
updated_at: 2026-03-27T09:07:26Z
---

## Summary

A separate PyPI package (`hyperadmin-logfire`) that instruments HyperAdmin with Pydantic Logfire for per-model CRUD latency, query performance, form validation failure rates, and auth event tracing. One-call setup, zero changes to HyperAdmin core. **The first official plugin — proves the plugin architecture.**

Parent: #270

## Motivation

- Admin panels hide performance problems — slow list queries, N+1 issues, validation bottlenecks — until users complain
- Logfire is built by the Pydantic team, making it the natural observability partner for a Pydantic-native admin
- This plugin serves as the **proof-of-concept for HyperAdmin's plugin system** — if it works cleanly without core changes, the plugin architecture is validated
- No Python admin framework has a first-party observability plugin

## Integration: One Call

```python
import logfire
from hyperadmin_logfire import instrument_admin

logfire.configure()
admin = Admin(app, engine=engine)
instrument_admin(admin)  # <-- one call does everything
admin.mount("/admin")
```

`instrument_admin()` does:
1. `logfire.instrument_fastapi(admin.app)` — auto-instrument all HTTP requests
2. `logfire.instrument_sqlalchemy(engine=admin.engine)` — auto-instrument all SQL queries
3. Wrap each registered adapter with `InstrumentedAdapter` proxy — admin-specific CRUD spans
4. Optionally add ASGI middleware for user identity enrichment

## Architecture

```
hyperadmin-logfire/
  src/hyperadmin_logfire/
    __init__.py          # Public API: instrument_admin()
    middleware.py         # Enriches request spans with model/action/user
    adapter_wrapper.py   # InstrumentedAdapter proxy (wraps BaseAdapter)
    dashboard.py         # (Phase 2) Performance widget data endpoint
```

**Key design**: Uses the proxy/decorator pattern on `BaseAdapter` — no subclassing, no core changes. The proxy wraps any concrete adapter and adds `logfire.span()` around each method:

```python
class InstrumentedAdapter(BaseAdapter):
    def __init__(self, inner: BaseAdapter): ...

    async def list(self, **kwargs):
        with logfire.span("admin.adapter.list", model=self.model_name, **kwargs):
            return await self._inner.list(**kwargs)

    async def create(self, data):
        with logfire.span("admin.adapter.create", model=self.model_name):
            return await self._inner.create(data)
```

## Key Features

### A. Adapter Call Timing (per-model, per-operation)

Wraps all 7 `BaseAdapter` methods with `logfire.span()`:
- `admin.adapter.get` / `admin.adapter.list` / `admin.adapter.create` / `admin.adapter.update` / `admin.adapter.delete` / `admin.adapter.get_choices`
- Each span includes: `model`, `operation`, `page`, `page_size`, `search`, `filters`
- Gives per-model p50/p95/p99 latency histograms in the Logfire dashboard

### B. Query Performance per Model

Already provided by `logfire.instrument_sqlalchemy()`. Combined with adapter spans as parents, you get the full tree:

```
HTTP request → adapter.list → SELECT ... FROM products WHERE ...
```

Logfire SQL interface can aggregate by model, enabling "Products list is 3x slower than Orders list" insights.

### C. Form Validation Failure Rates

Emit structured log events when `PydanticForm.validate()` returns errors:

```python
logfire.warn("admin.validation_error", model=model_name, field_errors=errors)
```

Enables dashboards: validation failure rate per model, most-failing fields, error message distribution.

### D. Auth Events

Middleware emits:
- `admin.auth.login_success` / `admin.auth.login_failure`
- `admin.auth.logout`
- `admin.auth.permission_denied` (with codename)

### E. Slow CRUD Alerts

Logfire's built-in alerting can trigger on span duration — e.g., "adapter.list for Products took > 500ms". Zero custom code needed.

## Comparable Tools

| Tool | Framework | Approach | Difference |
|------|-----------|----------|------------|
| **django-silk** | Django | Middleware + local DB storage + own UI (`/silk/`) | Local storage overhead, own UI maintenance |
| **Django Debug Toolbar** | Django | In-page dev toolbar, SQL/template panels | Dev-only, not production |
| **Sentry** | Any | OTel tracing, error tracking | Generic, no admin-specific spans |

**`hyperadmin-logfire` advantage**: Zero local storage — sends data to Logfire (or any OTel backend). Leverages Logfire's dashboard, SQL queries, and alerting. Since Logfire SDK is OpenTelemetry-compatible, users can export to Jaeger, Grafana Tempo, or Datadog instead.

## Performance Dashboard Widget (Phase 2)

A future in-admin dashboard widget could query Logfire's API for aggregated stats:
- p50/p95/p99 latency per model per operation
- Slow queries list
- Validation error rates
- Recent auth events

**Alternative**: Local OpenTelemetry metrics via `logfire.metric_counter()` / `logfire.metric_histogram()` — no external API call needed. Render via HTMX partial on dashboard template.

This is Phase 2 of the plugin, not the MVP.

## Package Structure

```toml
# pyproject.toml
[project]
name = "hyperadmin-logfire"
dependencies = ["hyper-admin>=0.2.0", "logfire>=4.0"]

[project.entry-points."hyperadmin.plugins"]
logfire = "hyperadmin_logfire:LogfirePlugin"
```

## Integration Points (No Core Changes Required)

| Point | Mechanism | Instruments |
|-------|-----------|-------------|
| `logfire.instrument_fastapi(app)` | OTel auto-instrumentation | HTTP requests, arg parsing, endpoint timing |
| `logfire.instrument_sqlalchemy(engine)` | OTel auto-instrumentation | All SQL queries with duration/text |
| `InstrumentedAdapter` proxy | Adapter composition pattern | Admin CRUD spans with model/operation/user |
| ASGI middleware (optional) | Starlette middleware | Request enrichment with admin context |

## Open Questions

- [ ] **Naming**: `hyperadmin-logfire` (Logfire-branded) or `hyperadmin-otel` (generic OpenTelemetry)? Former is simpler, latter is more flexible.
- [ ] **Core lifecycle hooks**: Should HyperAdmin core expose `on_before_adapter_call` / `on_after_adapter_call` hooks to make plugin integration cleaner? Would benefit all future plugins.
- [ ] **Pydantic validation scope**: `logfire.instrument_pydantic()` traces ALL validations (noisy). Scope to admin form models only via `PydanticForm.validate()`?
- [ ] **Production overhead**: FastAPI + SQLAlchemy auto-instrumentation adds measurable per-request overhead. Document benchmarks + sampling rate guidance.
- [ ] **Dashboard API dependency**: Does Logfire expose a stable REST API for querying span data? If not, dashboard widget falls back to local OTel metrics.
- [ ] **Closed-source dashboard**: Logfire dashboard is SaaS. Document Jaeger/Grafana as open-source alternative export targets.

## References

- [Pydantic Logfire](https://pydantic.dev/logfire) — official site
- [Logfire FastAPI Integration](https://logfire.pydantic.dev/docs/integrations/web-frameworks/fastapi/)
- [Logfire SQLAlchemy Integration](https://logfire.pydantic.dev/docs/integrations/databases/sqlalchemy/)
- [Logfire GitHub (MIT)](https://github.com/pydantic/logfire)
- [django-silk](https://github.com/jazzband/django-silk) — comparable Django tool

---
https://claude.ai/code/session_01XktRz2PFThVGgPMoUmaEjc
