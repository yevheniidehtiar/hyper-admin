"""Centralised configuration for HyperAdmin via pydantic-settings BaseSettings."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "hyperadmin-default-secret"  # noqa: S105
_DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

ThemeLiteral = Literal["auto", "light", "dark"]


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

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = _DEFAULT_DATABASE_URL

    # ── Runtime behaviour ─────────────────────────────────────────────────────
    debug: bool = False
    create_tables: bool = True

    # ── Discovery ─────────────────────────────────────────────────────────────
    auto_discover: bool = False
    discover_apps: list[str] = Field(default_factory=list)

    # ── Templates ─────────────────────────────────────────────────────────────
    template_dirs: list[str] = Field(default_factory=list)

    # ── UI ────────────────────────────────────────────────────────────────────
    theme: ThemeLiteral = "auto"
    items_per_page: int = Field(default=20, gt=0)

    # ── Uploads ───────────────────────────────────────────────────────────────
    upload_dir: str = "uploads"

    # ── Formatting ────────────────────────────────────────────────────────────
    date_format: str = "%Y-%m-%d"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def is_default_secret_key(self) -> bool:
        """Return ``True`` when ``secret_key`` has not been changed from the default."""
        return self.secret_key == _DEFAULT_SECRET_KEY

    @field_validator("theme", mode="before")
    @classmethod
    def _validate_theme(cls, value: str) -> str:
        valid = ("auto", "light", "dark")
        if value not in valid:
            msg = f"Invalid theme {value!r}. Must be one of {valid}"
            raise ValueError(msg)
        return value
