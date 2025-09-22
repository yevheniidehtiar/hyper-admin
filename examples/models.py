from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    email: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    rating: float = 0.0
    user_type: str = "standard"
