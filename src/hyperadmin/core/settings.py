"""Centralised configuration for HyperAdmin via pydantic-settings BaseSettings."""

from functools import lru_cache
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

from hyperadmin.core.csrf import CsrfMode

_DEFAULT_SECRET_KEY = "hyperadmin-default-secret"  # noqa: S105
_DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
_DEFAULT_SUPPORTED_LOCALES = [
    # Original v0.4.1 set (LTR, ordered by speaker count + admin-UI relevance).
    "en",
    "es",
    "fr",
    "de",
    "zh_CN",
    "ja",
    "uk",
    # v0.5.2 top-20 expansion: 2 RTL + 1 Devanagari + European + SE-Asian.
    "ar",
    "he",
    "hi",
    "pt_BR",
    "ru",
    "ko",
    "it",
    "tr",
    "pl",
    "nl",
    "vi",
    "id",
    "th",
]

ThemeLiteral = Literal["auto", "light", "dark"]
MountModeLiteral = Literal["isolated", "router"]
StorageBackendLiteral = Literal["local", "s3"]
#: ``cookie_secure`` setting values (SDD C.4).
CookieSecure = Literal["auto"] | bool
SameSiteLiteral = Literal["lax", "strict", "none"]

#: Request schemes whose cookies get ``Secure`` under ``cookie_secure="auto"``.
_SECURE_SCHEMES = frozenset({"https", "wss"})


def resolve_cookie_secure(cookie_secure: CookieSecure, scheme: str) -> bool:
    """Return whether an admin cookie gets the ``Secure`` flag (SDD C.4).

    ``True`` / ``False`` are used as-is. ``"auto"`` follows the effective request
    scheme (``request.url.scheme``, which honours ``X-Forwarded-Proto`` when the
    server trusts the proxy), so plain-http installs and ``TestClient`` keep their
    cookies while https/wss requests get ``Secure``.
    """
    if cookie_secure == "auto":
        return scheme.lower() in _SECURE_SCHEMES
    return cookie_secure is True


@lru_cache(maxsize=1)
def _available_timezones() -> frozenset[str]:
    """Return the canonical IANA zone keys known on this host (cached)."""
    return frozenset(available_timezones())


class HyperAdminSettings(BaseSettings):
    """Django-like centralised settings for HyperAdmin.

    All scalar configuration lives here — no duplicate params on ``Admin()``.
    Values can be provided via environment variables (``HYPERADMIN_*`` prefix),
    a ``.env`` file, or explicit keyword arguments (highest priority).

    Example::

        settings = HyperAdminSettings(secret_key="my-secret", theme="dark")
        Admin(app, engine=engine, settings=settings)

        # Or rely entirely on env vars / .env:
        Admin(app, engine=engine)
    """

    model_config = SettingsConfigDict(
        env_prefix="HYPERADMIN_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Branding ─────────────────────────────────────────────────────────────
    site_title: str = "HyperAdmin"
    site_header: str = "HyperAdmin"

    # ── Security ─────────────────────────────────────────────────────────────
    secret_key: str = Field(default=_DEFAULT_SECRET_KEY)

    # ── CSRF (SDD D.1) ──────────────────────────────────────────────────────────
    #: ``"auto"`` enforces the signed double-submit check whenever auth is
    #: configured and is off otherwise; ``"report"`` only logs failures.
    csrf_mode: CsrfMode = "auto"
    csrf_cookie_name: str = Field(default="hyperadmin_csrf", min_length=1)
    csrf_header_name: str = Field(default="X-CSRF-Token", min_length=1)
    csrf_field_name: str = Field(default="csrf_token", min_length=1)
    #: Extra origins (``"https://admin.example"``) the ``Origin`` check accepts.
    csrf_trusted_origins: list[str] = Field(default_factory=list)
    #: ``Secure`` flag for every admin cookie (session, CSRF, token, locale; SDD C.4):
    #: ``"auto"`` follows the effective request scheme; set ``True`` behind a TLS
    #: proxy uvicorn does not trust.
    cookie_secure: CookieSecure = "auto"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = _DEFAULT_DATABASE_URL
    #: Connection pool of the engine HyperAdmin builds from ``database_url`` (no
    #: ``engine=`` passed); a host engine keeps its own pool. ``None`` keeps
    #: SQLAlchemy's default. The ``pool_*`` sizes are ignored for in-memory SQLite.
    database_pool_size: int | None = Field(default=None, ge=1)
    #: Connections opened above ``database_pool_size`` under load; ``-1`` is unlimited.
    database_max_overflow: int | None = Field(default=None, ge=-1)
    #: Seconds a request waits for a free connection before it fails.
    database_pool_timeout: float | None = Field(default=None, gt=0)
    #: Seconds after which a connection is replaced; ``-1`` never replaces it.
    database_pool_recycle: int | None = Field(default=None, ge=-1)
    #: Test each connection before use, so ones the server dropped are replaced.
    database_pool_pre_ping: bool = False

    # ── Runtime behaviour ─────────────────────────────────────────────────────
    debug: bool = False
    #: Defaults to ``False`` (SDD C.2): a host engine or session_factory never gets DDL
    #: run against it unless requested. Demo mode (no engine=, no session_factory=) is
    #: the one exception — it still auto-creates tables when database_url is SQLite, so
    #: zero-config ``Admin(app).mount("/admin")`` keeps working. Set this to ``True`` to
    #: keep the old "always create every table at startup" behaviour.
    create_tables: bool = False
    #: Register the built-in ``User``/``Group``/``Permission`` admins (SDD B.3).
    #: ``None`` (default) means on with ``auth_backend=`` and off with ``auth=``
    #: (bring-your-own-auth) or no auth; ``True``/``False`` force it either way.
    register_auth_models: bool | None = None

    # ── Mounting (SDD C.1) ──────────────────────────────────────────────────────
    #: ``"isolated"`` (default) attaches the admin as a private sub-application, so
    #: its middleware, static files, route names and OpenAPI stay out of the host.
    #: ``"router"`` is the deprecated legacy mode (``include_router`` + global
    #: middleware), removed in 0.6.
    mount_mode: MountModeLiteral = "isolated"
    #: Name of the sub-application mount; admin routes resolve as
    #: ``f"{route_namespace}:{name}"`` (e.g. ``hyperadmin:user-list``) in isolated mode.
    route_namespace: str = Field(default="hyperadmin", min_length=1, pattern=r"^[^:/]+$")

    # ── Admin cookies (SDD C.4) ─────────────────────────────────────────────────
    #: Name of the admin's own session cookie. Its ``Path`` is the per-request admin
    #: path, so it never collides with a host ``session`` cookie. In the deprecated
    #: router mode the legacy cookie (``session``, ``Path=/``) is kept unless this
    #: is set explicitly.
    session_cookie: str = Field(default="hyperadmin_session", min_length=1)
    #: Session lifetime in seconds (default: 14 days).
    session_max_age: int = Field(default=1_209_600, gt=0)
    session_same_site: SameSiteLiteral = "lax"
    #: Seconds the authenticated user and its permission set are cached per worker,
    #: keyed by session user id (``0`` = off: loaded on every request). Writes on the
    #: same worker invalidate the entry; other workers may serve a stale user for up
    #: to this many seconds.
    user_cache_ttl: int = Field(default=0, ge=0)

    # ── Discovery ─────────────────────────────────────────────────────────────
    auto_discover: bool = False
    discover_apps: list[str] = Field(default_factory=list)
    #: Load ``hyperadmin.plugins`` entry points when the ``Admin`` is built. ``False``
    #: skips discovery entirely; plugins can still be registered by hand with
    #: ``admin.plugins.register(plugin, admin=admin)`` before ``mount()``.
    plugins_enabled: bool = True

    # ── Permission matrix (docs/specs/permission-matrix-ui.md) ───────────────
    #: Register the ``{prefix}/permissions-matrix/`` page and its sidebar entry.
    #: ``False`` leaves the URL unrouted (404) for projects without groups.
    permissions_matrix_enabled: bool = True
    #: Codename an operator needs to open and save the matrix (superusers always
    #: may). Synced into ``hyperadmin_permissions`` next to the plugin codenames.
    permissions_matrix_codename: str = Field(
        default="change_groups_permissions", min_length=1, pattern=r"^[a-z][a-z0-9_]*$"
    )

    # ── Templates ─────────────────────────────────────────────────────────────
    template_dirs: list[str] = Field(default_factory=list)

    # ── UI ────────────────────────────────────────────────────────────────────
    theme: ThemeLiteral = "auto"
    items_per_page: int = Field(default=20, gt=0)

    # ── Uploads ───────────────────────────────────────────────────────────────
    upload_dir: str = "uploads"
    #: Escape hatch (SDD C.5): when set, the storage directory is also mounted
    #: publicly at this host path, outside the admin's authentication, and a
    #: startup warning is logged. Files are otherwise served only per record at
    #: ``{prefix}/{model}/{item_id}/file/{field}``.
    public_uploads_path: str | None = Field(default=None, pattern=r"^/[^\s]*[^/\s]$")

    # ── Uploads: S3-compatible object storage (epic #410, story #402) ──────────
    #: ``"s3"`` makes ``Admin()`` build an ``S3StorageBackend`` from the ``aws_*``
    #: settings when no ``storage=`` is passed (needs ``pip install 'hyper-admin[s3]'``).
    #: ``"local"`` (default) leaves the choice to the host: uploads stay off until
    #: a ``FileSystemStorage`` is passed.
    storage_backend: StorageBackendLiteral = "local"
    #: Every ``aws_*`` setting reads ``HYPERADMIN_AWS_*`` first and then the plain
    #: ``AWS_*`` variable the AWS SDK and ``fastapi-storages`` use, so one set of
    #: variables configures both. Credentials are optional: when unset, boto3's
    #: own chain applies (profiles, instance and task roles).
    aws_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("hyperadmin_aws_access_key_id", "aws_access_key_id"),
    )
    aws_secret_access_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("hyperadmin_aws_secret_access_key", "aws_secret_access_key"),
    )
    aws_s3_bucket_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("hyperadmin_aws_s3_bucket_name", "aws_s3_bucket_name"),
    )
    aws_s3_region: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "hyperadmin_aws_s3_region", "aws_s3_region", "aws_default_region"
        ),
    )
    #: ``http(s)://host[:port]`` of an S3-compatible service (MinIO, R2, Hetzner,
    #: Spaces); unset for AWS S3.
    aws_s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("hyperadmin_aws_s3_endpoint_url", "aws_s3_endpoint_url"),
    )
    #: Host object URLs are served from instead of the endpoint (CDN, R2 public
    #: bucket domain); such URLs are not signed.
    aws_s3_custom_domain: str | None = Field(
        default=None,
        validation_alias=AliasChoices("hyperadmin_aws_s3_custom_domain", "aws_s3_custom_domain"),
    )
    #: Sign object URLs (presigned, time-limited). ``False`` only for a
    #: public-read bucket.
    aws_s3_querystring_auth: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "hyperadmin_aws_s3_querystring_auth", "aws_s3_querystring_auth", "aws_querystring_auth"
        ),
    )
    #: ACL set on every written object (``"public-read"``); unset keeps objects
    #: private and sends no ACL (required by services without ACLs, such as R2).
    aws_s3_default_acl: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "hyperadmin_aws_s3_default_acl", "aws_s3_default_acl", "aws_default_acl"
        ),
    )

    # ── Formatting ────────────────────────────────────────────────────────────
    date_format: str = "%Y-%m-%d"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"
    #: IANA zone used to enter and display timezone-aware datetimes.
    timezone: str = "UTC"

    # ── Performance ───────────────────────────────────────────────────────────
    #: Most list totals the built-in count cache keeps; the least recently used go first.
    #: Only used by models that set ``AdminOptions.count_cache_ttl``.
    count_cache_max_entries: int = Field(default=1024, ge=1)
    #: Requests one client may make to the admin per ``rate_limit_window_seconds``;
    #: over that gets ``429``. ``None`` (default) applies no limit. Counted per process,
    #: so N workers allow up to N times this; pass ``Admin(rate_limiter=...)`` for a
    #: shared limiter. Static assets are never counted.
    rate_limit_requests: int | None = Field(default=None, ge=1)
    #: A further, normally stricter, limit on login form submissions per client, within
    #: the same window. ``None`` (default) applies none.
    rate_limit_login_requests: int | None = Field(default=None, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)

    # ── Concurrency (docs/specs/realtime-occ.md) ──────────────────────────────
    #: Let ``updated_at`` act as the version field of models with no ``version`` column.
    #: Approximate: writes within the column's timestamp resolution can go undetected.
    concurrency_use_updated_at: bool = False
    #: Render the HTML conflict dialog on a stale save; ``False`` answers API clients
    #: with a JSON 409 body instead.
    occ_render_dialog: bool = True

    # ── Navigation ────────────────────────────────────────────────────────────
    #: Most sidebar pages one user may pin (built-in or bridge auth only).
    nav_pins_max: int = Field(default=20, ge=1)

    # ── Internationalization ──────────────────────────────────────────────────
    default_locale: str = "en"
    supported_locales: list[str] = Field(default_factory=lambda: list(_DEFAULT_SUPPORTED_LOCALES))
    locale_response_header: bool = True

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def database_engine_kwargs(self) -> dict[str, Any]:
        """Return the ``create_async_engine`` pool arguments set by ``database_pool_*``."""
        kwargs: dict[str, Any] = {
            "pool_size": self.database_pool_size,
            "max_overflow": self.database_max_overflow,
            "pool_timeout": self.database_pool_timeout,
            "pool_recycle": self.database_pool_recycle,
        }
        kwargs = {key: value for key, value in kwargs.items() if value is not None}
        if self.database_pool_pre_ping:
            kwargs["pool_pre_ping"] = True
        return kwargs

    @property
    def is_default_secret_key(self) -> bool:
        """Return ``True`` when ``secret_key`` has not been changed from the default."""
        return self.secret_key == _DEFAULT_SECRET_KEY

    @property
    def tzinfo(self) -> ZoneInfo:
        """Return the configured display timezone as a ``ZoneInfo``."""
        return ZoneInfo(self.timezone)

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            msg = f"Invalid timezone {value!r}. Must be an IANA zone name such as 'UTC'"
            raise ValueError(msg) from exc
        # A case-insensitive filesystem (macOS) resolves 'utc' too; Linux and the
        # Windows tzdata package do not, so require the canonical spelling.
        known = _available_timezones()
        if known and value not in known:
            canonical = next((key for key in known if key.lower() == value.lower()), None)
            hint = f" Did you mean {canonical!r}?" if canonical else ""
            msg = f"Invalid timezone {value!r}. Zone names are case-sensitive.{hint}"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_storage_backend(self) -> Self:
        if self.storage_backend == "s3" and not self.aws_s3_bucket_name:
            msg = (
                "storage_backend='s3' requires aws_s3_bucket_name "
                "(HYPERADMIN_AWS_S3_BUCKET_NAME or AWS_S3_BUCKET_NAME)"
            )
            raise ValueError(msg)
        return self

    @field_validator("theme", mode="before")
    @classmethod
    def _validate_theme(cls, value: str) -> str:
        valid = ("auto", "light", "dark")
        if value not in valid:
            msg = f"Invalid theme {value!r}. Must be one of {valid}"
            raise ValueError(msg)
        return value
