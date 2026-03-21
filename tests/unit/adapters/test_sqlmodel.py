import pytest
from examples.simple.models import User
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, Relationship, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin.adapters.sqlmodel import SQLModelAdapter


class Post(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    content: str
    comments: list["Comment"] = Relationship(back_populates="post")


class Comment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    text: str
    post_id: int | None = Field(default=None, foreign_key="post.id")
    post: Post | None = Relationship(back_populates="comments")


@pytest.fixture
async def engine():
    """
    Creates an in-memory SQLite database engine for testing.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


@pytest.fixture
async def session(engine):
    """
    Creates a session for interacting with the test database.
    """
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture
async def adapter(engine):
    """
    Creates an instance of SQLModelAdapter for testing.
    """
    return SQLModelAdapter(model=User, engine=engine)


@pytest.fixture
async def post_adapter(engine):
    return SQLModelAdapter(model=Post, engine=engine)


@pytest.mark.anyio
async def test_adapter_creation(adapter: SQLModelAdapter):
    """
    Tests that the adapter can be created successfully.
    """
    assert isinstance(adapter, SQLModelAdapter)
    assert adapter.model == User


@pytest.mark.anyio
async def test_create(adapter: SQLModelAdapter, session: AsyncSession):
    """
    Tests that the create method correctly adds a new user to the database.
    """
    user_data = {"name": "Jules", "email": "jules@example.com"}
    created_user = await adapter.create(user_data)

    assert created_user.id is not None
    assert created_user.name == user_data["name"]
    assert created_user.email == user_data["email"]

    # Verify the user is in the database
    user_in_db = await session.get(User, created_user.id)
    assert user_in_db is not None
    assert user_in_db.name == user_data["name"]


@pytest.mark.anyio
async def test_get(adapter: SQLModelAdapter, session: AsyncSession):
    """
    Tests that the get method can retrieve a user by their primary key.
    """
    user_data = {"name": "Jules", "email": "jules@example.com"}
    created_user = await adapter.create(user_data)

    retrieved_user = await adapter.get(pk=created_user.id)

    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.name == created_user.name


@pytest.mark.anyio
async def test_list_basic(adapter: SQLModelAdapter, session: AsyncSession):
    """
    Tests that the list method can retrieve a list of users.
    """
    # Create some users
    user1_data = {"name": "Jules", "email": "jules@example.com"}
    user2_data = {"name": "Jane", "email": "jane@example.com"}
    await adapter.create(user1_data)
    await adapter.create(user2_data)

    users, total_count = await adapter.list()

    assert total_count == len(users)
    assert users[0].name == "Jules"
    assert users[1].name == "Jane"


@pytest.mark.anyio
async def test_list_pagination(adapter: SQLModelAdapter, session: AsyncSession):
    """
    Tests that the list method supports pagination.
    """
    # Create 3 users
    for i in range(3):
        await adapter.create({"name": f"User {i}", "email": f"user{i}@example.com"})

    # Get the first page
    users, total_count = await adapter.list(page=1, page_size=2)
    assert total_count == 3
    assert len(users) == 2
    assert users[0].name == "User 0"
    assert users[1].name == "User 1"

    # Get the second page
    users, total_count = await adapter.list(page=2, page_size=2)
    assert total_count == 3
    assert len(users) == 1
    assert users[0].name == "User 2"


@pytest.mark.anyio
async def test_list_ordering(adapter: SQLModelAdapter, session: AsyncSession):
    """
    Tests that the list method supports ordering.
    """
    # Create some users
    await adapter.create({"name": "Jules", "email": "jules@example.com"})
    await adapter.create({"name": "Jane", "email": "jane@example.com"})
    await adapter.create({"name": "Adam", "email": "adam@example.com"})

    # Test ascending order
    users, _ = await adapter.list(order_by="name")
    assert [user.name for user in users] == ["Adam", "Jane", "Jules"]

    # Test descending order
    users, _ = await adapter.list(order_by="-name")
    assert [user.name for user in users] == ["Jules", "Jane", "Adam"]


@pytest.mark.anyio
async def test_list_search_and_filter(adapter: SQLModelAdapter, session: AsyncSession):
    """
    Tests that the list method supports searching and filtering.
    """
    await adapter.create({"name": "Jules", "email": "jules@example.com"})
    await adapter.create({"name": "Jane", "email": "jane@example.com"})
    await adapter.create({"name": "Adam", "email": "adam@another.com"})

    # Test filtering
    users, total_count = await adapter.list(filters={"email": "jules@example.com"})
    assert total_count == 1
    assert len(users) == 1
    assert users[0].name == "Jules"

    # Test searching
    users, total_count = await adapter.list(search="j")
    assert total_count == len(users)
    assert users[0].name == "Jules"
    assert users[1].name == "Jane"

    # Test searching with case-insensitivity
    users, total_count = await adapter.list(search="J")
    assert total_count == len(users)
    assert len(users) == 2


@pytest.mark.anyio
async def test_update(adapter: SQLModelAdapter, session: AsyncSession):
    """
    Tests that the update method correctly updates a user in the database.
    """
    user_data = {"name": "Jules", "email": "jules@example.com"}
    created_user = await adapter.create(user_data)

    updated_data = {"name": "Julian"}
    updated_user = await adapter.update(pk=created_user.id, data=updated_data)

    assert updated_user.name == updated_data["name"]

    # Verify the user is updated in the database
    user_in_db = await session.get(User, created_user.id)
    assert user_in_db.name == updated_data["name"]


@pytest.mark.anyio
async def test_update_not_found(adapter: SQLModelAdapter):
    """
    Tests that the update method does nothing when the user is not found.
    """
    updated_user = await adapter.update(pk=999, data={"name": "Ghost"})
    assert updated_user is None


@pytest.mark.anyio
async def test_delete(adapter: SQLModelAdapter, session: AsyncSession):
    """
    Tests that the delete method correctly removes a user from the database.
    """
    user_data = {"name": "Jules", "email": "jules@example.com"}
    created_user = await adapter.create(user_data)

    await adapter.delete(pk=created_user.id)

    # Verify the user is deleted from the database
    user_in_db = await session.get(User, created_user.id)
    assert user_in_db is None


@pytest.mark.anyio
async def test_delete_not_found(adapter: SQLModelAdapter):
    """
    Tests that the delete method does nothing when the user is not found.
    """
    # This should not raise any exception
    await adapter.delete(pk=999)


@pytest.mark.anyio
async def test_get_related(post_adapter: SQLModelAdapter, session: AsyncSession):
    """
    Tests that the get_related method correctly retrieves related objects.
    """
    post = Post(title="Test Post", content="Test Content")
    comment1 = Comment(text="Test Comment 1", post=post)
    comment2 = Comment(text="Test Comment 2", post=post)

    session.add(post)
    session.add(comment1)
    session.add(comment2)
    await session.commit()
    await session.refresh(post)

    related_comments = await post_adapter.get_related(pk=post.id, field="comments")

    assert len(related_comments) == 2
    assert related_comments[0].text == "Test Comment 1"
    assert related_comments[1].text == "Test Comment 2"


@pytest.mark.anyio
async def test_get_related_not_found(post_adapter: SQLModelAdapter):
    """
    Tests that get_related returns an empty list when the object is not found.
    """
    related_items = await post_adapter.get_related(pk=999, field="comments")
    assert related_items == []


@pytest.mark.anyio
async def test_get_schema(adapter: SQLModelAdapter):
    """
    Tests that the get_schema method correctly returns the JSON schema of the model.
    """
    schema = await adapter.get_schema()
    assert isinstance(schema, dict)
    assert "title" in schema
    assert schema["title"] == "User"
    assert "properties" in schema
    assert "id" in schema["properties"]
    assert "name" in schema["properties"]
    assert "email" in schema["properties"]


@pytest.mark.anyio
async def test_list_eagerly_loads_relationships(post_adapter: SQLModelAdapter, engine):
    """Relationships are accessible after list() returns (session is closed)."""
    async with AsyncSession(engine) as session:
        post = Post(title="Eager Post", content="Content")
        session.add(post)
        await session.commit()
        await session.refresh(post)

        comment = Comment(text="Eager Comment", post_id=post.id)
        session.add(comment)
        await session.commit()

    items, total = await post_adapter.list()
    assert total == 1
    # Access the relationship outside the adapter's session — would raise
    # DetachedInstanceError without selectinload
    assert len(items[0].comments) == 1
    assert items[0].comments[0].text == "Eager Comment"


@pytest.mark.anyio
async def test_get_eagerly_loads_relationships(post_adapter: SQLModelAdapter, engine):
    """Relationships are accessible after get() returns (session is closed)."""
    async with AsyncSession(engine) as session:
        post = Post(title="Get Eager", content="Content")
        session.add(post)
        await session.commit()
        await session.refresh(post)
        post_id = post.id

        comment = Comment(text="Get Comment", post_id=post_id)
        session.add(comment)
        await session.commit()

    item = await post_adapter.get(pk=post_id)
    assert item is not None
    assert len(item.comments) == 1
    assert item.comments[0].text == "Get Comment"
