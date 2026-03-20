from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    """User model for authentication."""

    __tablename__ = "hyperadmin_users"  # type: ignore[reportIncompatibleVariableOverride]

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, max_length=50, unique=True)
    email: str = Field(index=True, max_length=100, unique=True)
    password_hash: str = Field(max_length=255)
    first_name: str = Field(default="", max_length=50)
    last_name: str = Field(default="", max_length=50)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)

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
    created_at: datetime = Field(default_factory=datetime.now)

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
    created_at: datetime = Field(default_factory=datetime.now)

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
