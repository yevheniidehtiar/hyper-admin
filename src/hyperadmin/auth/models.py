from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User model for authentication."""

    __tablename__ = "hyperadmin_users"  # type: ignore[reportIncompatibleVariableOverride]

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, max_length=50, unique=True)
    email: str = Field(index=True, max_length=100, unique=True)
    password_hash: str = Field(max_length=255)
    is_superuser: bool = Field(default=False)
