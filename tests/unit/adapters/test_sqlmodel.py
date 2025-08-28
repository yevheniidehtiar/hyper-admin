import pytest
from examples.models import User
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin.adapters.sqlmodel import SQLModelAdapter


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
async def adapter(session: AsyncSession):
    """
    Creates an instance of SQLModelAdapter for testing.
    """
    return SQLModelAdapter(model=User, session=session)


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
