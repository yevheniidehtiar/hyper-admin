import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select
from typer.testing import CliRunner

from hyperadmin.__main__ import app
from hyperadmin.auth import User

runner = CliRunner()


@pytest.fixture
def db_url(tmp_path):
    db_file = tmp_path / "test.db"
    return f"sqlite:///{db_file}"


@pytest.fixture
def setup_db(db_url):
    engine = create_engine(db_url)
    SQLModel.metadata.create_all(engine)
    return engine


def test_createsuperuser_success(db_url, setup_db):
    result = runner.invoke(
        app,
        [
            "createsuperuser",
            "--username",
            "admin",
            "--email",
            "admin@example.com",
            "--password",
            "password123",
            "--database-url",
            db_url,
        ],
    )
    assert result.exit_code == 0
    assert "Superuser 'admin' created successfully!" in result.stdout

    with Session(setup_db) as session:
        user = session.exec(select(User).where(User.username == "admin")).first()
        assert user is not None
        assert user.email == "admin@example.com"
        assert user.is_superuser is True
        assert user.password_hash.startswith("$argon2id$")


def test_createsuperuser_duplicate_username(db_url, setup_db):
    # Create first user
    runner.invoke(
        app,
        [
            "createsuperuser",
            "--username",
            "admin",
            "--email",
            "admin@example.com",
            "--password",
            "password123",
            "--database-url",
            db_url,
        ],
    )

    # Try creating with same username
    result = runner.invoke(
        app,
        [
            "createsuperuser",
            "--username",
            "admin",
            "--email",
            "admin2@example.com",
            "--password",
            "password123",
            "--database-url",
            db_url,
        ],
    )
    assert result.exit_code == 1
    assert "Error: User with username 'admin' already exists." in result.stderr


def test_createsuperuser_short_password(db_url, setup_db):
    result = runner.invoke(
        app,
        [
            "createsuperuser",
            "--username",
            "admin",
            "--email",
            "admin@example.com",
            "--password",
            "short",
            "--database-url",
            db_url,
        ],
    )
    assert result.exit_code == 1
    assert "Error: Password must be at least 8 characters long." in result.stderr


def test_createsuperuser_empty_email(db_url, setup_db):
    # Typer's CliRunner handles prompts by providing input
    result = runner.invoke(
        app,
        [
            "createsuperuser",
            "--username",
            "admin",
            "--email",
            "",
            "--password",
            "password123",
            "--database-url",
            db_url,
        ],
    )
    assert result.exit_code == 1
    assert "Error: Email cannot be empty." in result.stderr


def test_createsuperuser_interactive_success(db_url, setup_db):
    # Provide inputs for prompts
    result = runner.invoke(
        app,
        ["createsuperuser", "--database-url", db_url],
        input="admin\nadmin@example.com\npassword123\npassword123\n",
    )
    assert result.exit_code == 0
    assert "Superuser 'admin' created successfully!" in result.stdout


def test_createsuperuser_mismatched_password(db_url, setup_db):
    result = runner.invoke(
        app,
        ["createsuperuser", "--database-url", db_url],
        input="admin\nadmin@example.com\npassword123\nmismatched\n",
    )
    # Typer/Click will repeat prompt or exit on mismatch
    # By default Click prompts twice and exits if they don't match
    assert result.exit_code != 0
