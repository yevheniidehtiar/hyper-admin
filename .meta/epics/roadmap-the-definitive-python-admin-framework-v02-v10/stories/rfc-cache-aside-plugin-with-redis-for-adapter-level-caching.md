---
type: story
id: YfHG9fyjThjm
title: "RFC: Cache-aside plugin with Redis for adapter-level caching"
status: todo
priority: medium
assignee: null
labels:
  - performance
  - rfc
  - plugin
estimate: null
epic_ref:
  id: 5RQIGVbDMSTJ
github:
  issue_number: 271
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ddd44a965ae15cf496b0127c0890c2ed19e732d2d840f5324c3e0273447d4e15
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T09:02:15Z
updated_at: 2026-03-27T09:02:15Z
---

## Summary

A cache-aside plugin that wraps any `BaseAdapter` with transparent caching. Models can be marked as "heavy" (cache aggressively) or "external" (data from external JSON APIs, TTL-only invalidation). Redis as primary backend, in-memory fallback for dev/testing.

Parent: #270

## Motivation

Admin panels frequently query the same data (list pages, dropdown choices, detail views). For models with expensive queries, external API data sources, or high read:write ratios, caching eliminates redundant I/O and dramatically improves TTFB.

## Architecture: CachedAdapter Wrapper

Instead of decorators on individual methods, use a **proxy adapter** that wraps any `BaseAdapter`:

```python
class CachedAdapter(BaseAdapter):
    """Wraps any BaseAdapter with cache-aside logic."""
    def __init__(self, inner: BaseAdapter, cache: CacheBackend, config: CacheConfig): ...

    async def get(self, pk):
        key = f"ha:{self.model_name}:get:{pk}"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        result = await self.inner.get(pk)
        await self.cache.set(key, result, ttl=self.config.get_ttl)
        return result

    async def create(self, data):
        result = await self.inner.create(data)
        await self._invalidate_lists()  # pattern-based invalidation
        return result
```

This respects CONSTITUTION dependency direction — `CachedAdapter` lives in `adapters/`, implements `BaseAdapter`, requires zero changes to `core/`.

## Cache Key Schema

```
ha:{model}:get:{pk}                         # single object
ha:{model}:list:{sha256(canonical_params)}   # paginated list
ha:{model}:choices:{field}:{sha256(params)}  # FK/M2M dropdown choices
ha:{model}:related:{pk}:{field}              # related objects
```

- `ha:` prefix prevents collisions with other Redis users
- List params (page, page_size, search, filters, order_by) canonicalized → hashed

## Invalidation Strategy

| Mutation | Keys invalidated |
|----------|-----------------|
| `create(data)` | `ha:{model}:list:*`, `ha:{model}:choices:*` |
| `update(pk, data)` | `ha:{model}:get:{pk}`, `ha:{model}:list:*`, `ha:{model}:related:{pk}:*`, `ha:{model}:choices:*` |
| `delete(pk)` | `ha:{model}:get:{pk}`, `ha:{model}:list:*`, `ha:{model}:related:{pk}:*`, `ha:{model}:choices:*` |

- Uses Redis `SCAN` (not `KEYS`) for pattern-based invalidation
- Cross-model invalidation via explicit config: `invalidates=["country"]`

## Configuration

```python
class CacheConfig(BaseModel):
    enabled: bool = False
    get_ttl: int = 300       # seconds
    list_ttl: int = 60
    choices_ttl: int = 120
    profile: Literal["default", "heavy", "external"] = "default"
    invalidates: list[str] = []  # cross-model invalidation
```

**Profiles:**
- `default` — moderate TTLs, invalidate on write
- `heavy` — long TTLs (hours), for expensive queries or large datasets
- `external` — TTL-only invalidation, for data sourced from external JSON APIs

## Cache Backend Protocol

```python
class CacheBackend(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def delete_pattern(self, pattern: str) -> int: ...
```

Two implementations:
1. **`RedisCacheBackend`** — `redis.asyncio.Redis` (redis-py ≥4.2, successor to deprecated aioredis)
2. **`InMemoryCacheBackend`** — dict with TTL tracking, for dev/testing and single-process deployments

## Serialization

Use `orjson` + Pydantic `.model_dump()` → cache dict, reconstruct via `Model(**cached_dict)`. Avoids caching detached SQLAlchemy instances.

## Stampede Prevention

Lock-based approach using Redis `SET NX EX`. First request acquires lock, queries DB, populates cache. Others wait briefly or serve stale data. In-memory backend uses `asyncio.Lock`.

## External API Caching

For models backed by external APIs (not a database):
- **TTL-only invalidation** — no write-through
- **Stale-while-revalidate** — serve stale data while fetching fresh in background
- **Webhook-triggered invalidation** — expose endpoint that calls `cache.delete_pattern()`

## Module Structure

```
src/hyperadmin/
├── core/cache.py          # CacheBackend protocol (no imports from adapters/)
├── cache/
│   ├── __init__.py
│   ├── redis.py           # RedisCacheBackend
│   ├── memory.py          # InMemoryCacheBackend
│   └── adapter.py         # CachedAdapter wrapper
```

- `redis` as optional dependency: `pip install hyper-admin[cache]`
- `CacheBackend` protocol in `core/` must not import `redis`

## Open Questions

- [ ] Should cache config live on `AdminOptions` (per-model) or separate `CacheConfig` on `Admin.__init__()` with per-model overrides?
- [ ] Cache warming on startup for "heavy" models?
- [ ] Cache hit/miss metrics endpoint (`/admin/cache/stats`)?
- [ ] Multi-worker invalidation: in-memory is per-process — document Redis requirement for production?
- [ ] Interaction with planned audit log hooks (Phase 5)?

## Lessons from Django

Django's cache framework validates this approach: backend abstraction, `get_or_set()` atomicity, low-level API over middleware caching. HyperAdmin's adapter-level caching is analogous to Django's low-level cache API — correct because the same adapter data feeds multiple views.

---
https://claude.ai/code/session_01XktRz2PFThVGgPMoUmaEjc
