from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class UserType(str, Enum):
    STANDARD = "standard"
    ADMIN = "admin"


class ProductCategory(str, Enum):
    ELECTRONICS = "electronics"
    BOOKS = "books"
    CLOTHING = "clothing"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    email: str | None = None
    is_active: bool = True
    rating: float = 0.0
    user_type: UserType = Field(default=UserType.STANDARD, nullable=False)
    created_at: datetime | None = Field(default_factory=datetime.now)


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    description: str | None = None
    price: float = Field(gt=0)
    is_available: bool = True
    category: ProductCategory = Field(default=ProductCategory.ELECTRONICS, nullable=False)
    release_date: datetime | None = Field(default_factory=datetime.now)
