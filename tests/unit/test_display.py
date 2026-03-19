from sqlmodel import Field, SQLModel

from hyperadmin.core.display import get_display_name


def test_get_display_name_overridden_str():
    class CustomUser(SQLModel):
        name: str

        def __str__(self):
            return f"User: {self.name}"

    user = CustomUser(name="Alice")
    assert get_display_name(user) == "User: Alice"


def test_get_display_name_from_name_attr():
    class UserWithName(SQLModel):
        name: str

    user = UserWithName(name="Bob")
    assert get_display_name(user) == "Bob"


def test_get_display_name_from_title_attr():
    class Product(SQLModel):
        title: str

    product = Product(title="Widget")
    assert get_display_name(product) == "Widget"


def test_get_display_name_from_email_attr():
    class Profile(SQLModel):
        email: str

    profile = Profile(email="test@example.com")
    assert get_display_name(profile) == "test@example.com"


def test_get_display_name_fallback_to_pk():
    class LegacyModel(SQLModel):
        id: int | None = Field(default=None, primary_key=True)

    item = LegacyModel(id=123)
    assert get_display_name(item) == "LegacyModel (123)"


def test_get_display_name_final_fallback():
    class EmptyModel(SQLModel):
        pass

    item = EmptyModel()
    assert get_display_name(item) == "EmptyModel object"


def test_get_display_name_empty_attribute_fallback():
    class UserWithEmptyName(SQLModel):
        id: int = Field(primary_key=True)
        name: str

    user = UserWithEmptyName(id=1, name="")
    assert get_display_name(user) == "UserWithEmptyName (1)"
