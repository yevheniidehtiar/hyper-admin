from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str


class TestProduct(SQLModel, table=True):
    __tablename__ = "testproduct"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    price: float
