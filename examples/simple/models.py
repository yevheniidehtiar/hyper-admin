from datetime import datetime
from enum import Enum

from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType, ImageType
from sqlalchemy import Column
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

upload_storage = FileSystemStorage("uploads/")


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
    manual: str | None = Field(
        default=None,
        sa_column=Column(FileType(storage=upload_storage)),
    )
    photo: str | None = Field(
        default=None,
        sa_column=Column(ImageType(storage=upload_storage)),
    )


class Country(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)

    cities: Mapped[list["City"]] = Relationship(back_populates="country")

    def __str__(self) -> str:
        return self.name


class City(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    country_id: int | None = Field(default=None, foreign_key="country.id")

    country: Mapped[Country | None] = Relationship(back_populates="cities")

    def __str__(self) -> str:
        return self.name
