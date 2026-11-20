# API Reference

HyperAdmin's public API is organized into these modules:

| Module | Description |
|--------|-------------|
| [Application](application.md) | `Admin` class — the main entry point |
| [Views](views.md) | `ModelAdmin` / `AdminOptions` fields, `DynamicModelView`, `PydanticForm`, `HtmxWidget` |
| [Core Components](core.md) | `SiteRegistry`, `AdminOptions` |
| [Adapters](adapters.md) | `BaseAdapter`, `SQLModelAdapter`, `SQLAlchemyAdapter` |
| [Routing](routing.md) | `HyperAdminRouter` — URL generation |
| [Authentication & Permissions](auth.md) | `ExternalAuth`, `TokenCookie`, `SessionAuthBackend`, `ModelPermissionChecker`, `PermissionSyncService`, the built-in `User` / `Group` / `Permission` tables |
| [Plugins](plugins.md) | `Plugin`, `PluginRegistry`, `PluginError`, `LIFECYCLE_HOOKS` |
| [Uploads](uploads.md) | `S3StorageBackend`, `validate_upload` and the image helpers |
| [Realtime](realtime.md) | `RealtimeSettings`, `RealtimeEvent`, `RealtimeAction` |

What counts as public API, and what may change between releases, is described in
[Versioning & Deprecation](../versioning.md#what-is-public-api).

---

::: hyperadmin
