from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.auth._types import UTCNaiveDateTime, utc_now
from hyperadmin.auth.backend import is_password_usable
from hyperadmin.auth.oauth.tokens import token_cipher


class User(SQLModel, table=True):
    """User model for authentication."""

    __tablename__ = "hyperadmin_users"  # type: ignore[reportIncompatibleVariableOverride]

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, max_length=50, unique=True)
    email: str = Field(index=True, max_length=100, unique=True)
    password_hash: str = Field(
        max_length=255, schema_extra={"json_schema_extra": {"hyperadmin_sensitive": True}}
    )
    first_name: str = Field(default="", max_length=50)
    last_name: str = Field(default="", max_length=50)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    # MFA fields (additive, backward compatible — existing rows default to disabled, no
    # migration required). ``mfa_method`` is a free-form string rather than an Enum so
    # future methods (totp/sms/webauthn) can be added without a breaking schema change;
    # validation of allowed values lives in the service layer. For the MVP only "email"
    # is wired end-to-end — see docs/specs/object-permissions-mfa.md (Track B).
    mfa_enabled: bool = Field(default=False)
    mfa_method: str | None = Field(default=None, max_length=32)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)
    updated_at: datetime | None = Field(default=None, sa_type=UTCNaiveDateTime)

    user_groups: list["UserGroup"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "foreign_keys": "UserGroup.user_id",
            "lazy": "selectin",
        },
    )
    user_permissions: list["UserPermission"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "foreign_keys": "UserPermission.user_id",
            "lazy": "selectin",
        },
    )

    @property
    def oauth_only(self) -> bool:
        """``True`` when no password can sign this user in (created by an OAuth sign-in)."""
        return not is_password_usable(self.password_hash)

    def __str__(self) -> str:
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.username


class Group(SQLModel, table=True):
    """Group model for organizing users and assigning permissions."""

    __tablename__ = "hyperadmin_groups"  # type: ignore[reportIncompatibleVariableOverride]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=80, unique=True)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)
    # Optimistic-concurrency stamp of the permission matrix; see docs/specs/permission-matrix-ui.md
    permissions_version: int = Field(default=0, sa_column_kwargs={"server_default": "0"})

    user_groups: list["UserGroup"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={
            "foreign_keys": "UserGroup.group_id",
            "lazy": "selectin",
        },
    )
    group_permissions: list["GroupPermission"] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={
            "foreign_keys": "GroupPermission.group_id",
            "lazy": "selectin",
        },
    )

    def __str__(self) -> str:
        return self.name


class Permission(SQLModel, table=True):
    """Permission model with unique codename for authorization checks."""

    __tablename__ = "hyperadmin_permissions"  # type: ignore[reportIncompatibleVariableOverride]

    id: int | None = Field(default=None, primary_key=True)
    codename: str = Field(index=True, max_length=100, unique=True)
    name: str = Field(max_length=200)
    content_type: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)

    user_permissions: list["UserPermission"] = Relationship(
        back_populates="permission",
        sa_relationship_kwargs={
            "foreign_keys": "UserPermission.permission_id",
            "lazy": "selectin",
        },
    )
    group_permissions: list["GroupPermission"] = Relationship(
        back_populates="permission",
        sa_relationship_kwargs={
            "foreign_keys": "GroupPermission.permission_id",
            "lazy": "selectin",
        },
    )

    def __str__(self) -> str:
        return self.name


class UserGroup(SQLModel, table=True):
    """Junction table: User <-> Group."""

    __tablename__ = "hyperadmin_user_groups"  # type: ignore[reportIncompatibleVariableOverride]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="hyperadmin_users.id", index=True)
    group_id: int = Field(foreign_key="hyperadmin_groups.id", index=True)

    user: User | None = Relationship(
        back_populates="user_groups",
        sa_relationship_kwargs={"foreign_keys": "UserGroup.user_id"},
    )
    group: Group | None = Relationship(
        back_populates="user_groups",
        sa_relationship_kwargs={"foreign_keys": "UserGroup.group_id"},
    )


class UserPermission(SQLModel, table=True):
    """Junction table: User <-> Permission (direct grants)."""

    __tablename__ = "hyperadmin_user_permissions"  # type: ignore[reportIncompatibleVariableOverride]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="hyperadmin_users.id", index=True)
    permission_id: int = Field(foreign_key="hyperadmin_permissions.id", index=True)

    user: User | None = Relationship(
        back_populates="user_permissions",
        sa_relationship_kwargs={"foreign_keys": "UserPermission.user_id"},
    )
    permission: Permission | None = Relationship(
        back_populates="user_permissions",
        sa_relationship_kwargs={"foreign_keys": "UserPermission.permission_id"},
    )


class GroupPermission(SQLModel, table=True):
    """Junction table: Group <-> Permission."""

    __tablename__ = "hyperadmin_group_permissions"  # type: ignore[reportIncompatibleVariableOverride]

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="hyperadmin_groups.id", index=True)
    permission_id: int = Field(foreign_key="hyperadmin_permissions.id", index=True)

    group: Group | None = Relationship(
        back_populates="group_permissions",
        sa_relationship_kwargs={"foreign_keys": "GroupPermission.group_id"},
    )
    permission: Permission | None = Relationship(
        back_populates="group_permissions",
        sa_relationship_kwargs={"foreign_keys": "GroupPermission.permission_id"},
    )


class OAuthToken(SQLModel, table=True):
    """Tokens of one user at one OAuth2/OIDC identity provider, encrypted at rest.

    A row is also the link between a ``User`` and an identity: ``(provider, sub)``
    is unique, and so is ``(user_id, provider)``. Only ciphertext is stored; the
    ``access_token`` and ``refresh_token`` properties encrypt on write and decrypt
    on read with the key of ``hyperadmin.auth.oauth.tokens``. The table is created
    and used only by hosts that enable OAuth. See ``docs/specs/oauth-sso.md``.
    """

    __tablename__ = "hyperadmin_oauth_tokens"  # type: ignore[reportIncompatibleVariableOverride]
    __table_args__ = (
        UniqueConstraint("provider", "sub", name="uq_oauth_provider_sub"),
        UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="hyperadmin_users.id", index=True)
    provider: str = Field(max_length=32, index=True)
    #: The provider's stable id of the user (OIDC ``sub``, GitHub numeric ``id``).
    sub: str = Field(max_length=255, index=True)
    access_token_encrypted: bytes = Field(default=b"")
    refresh_token_encrypted: bytes | None = Field(default=None)
    expires_at: datetime | None = Field(default=None, sa_type=UTCNaiveDateTime)
    scopes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)
    updated_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)

    user: User | None = Relationship(
        sa_relationship_kwargs={"foreign_keys": "OAuthToken.user_id", "lazy": "selectin"},
    )

    def __init__(self, **data: Any) -> None:
        """Accept plaintext ``access_token`` / ``refresh_token`` next to the columns."""
        access_token = data.pop("access_token", None)
        refresh_token = data.pop("refresh_token", None)
        super().__init__(**data)
        if access_token is not None:
            self.access_token = access_token
        if refresh_token is not None:
            self.refresh_token = refresh_token

    @property
    def access_token(self) -> str:
        """The decrypted access token."""
        return token_cipher().decrypt(self.access_token_encrypted)

    @access_token.setter
    def access_token(self, value: str) -> None:
        self.access_token_encrypted = token_cipher().encrypt(value)

    @property
    def refresh_token(self) -> str | None:
        """The decrypted refresh token, or ``None`` when the provider issued none."""
        if self.refresh_token_encrypted is None:
            return None
        return token_cipher().decrypt(self.refresh_token_encrypted)

    @refresh_token.setter
    def refresh_token(self, value: str | None) -> None:
        self.refresh_token_encrypted = None if value is None else token_cipher().encrypt(value)

    def __str__(self) -> str:
        return f"{self.provider}:{self.sub}"
