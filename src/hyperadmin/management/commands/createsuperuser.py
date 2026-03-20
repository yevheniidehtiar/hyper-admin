from typing import Annotated

import typer
from sqlalchemy import create_engine
from sqlmodel import Session, select

from hyperadmin.auth import User, hash_password

app = typer.Typer(help="Management commands for HyperAdmin.")


@app.command()
def createsuperuser(
    username: Annotated[
        str,
        typer.Option(
            "--username",
            prompt=True,
            help="The username of the superuser.",
        ),
    ],
    email: Annotated[
        str,
        typer.Option(
            "--email",
            prompt=True,
            help="The email of the superuser.",
        ),
    ],
    password: Annotated[
        str,
        typer.Option(
            "--password",
            prompt=True,
            confirmation_prompt=True,
            hide_input=True,
            help="The password of the superuser.",
        ),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(
            "--database-url",
            envvar="DATABASE_URL",
            help="The database URL to use.",
        ),
    ] = None,
):
    """Creates a superuser with the given username, email, and password."""
    # Validation logic
    if not database_url:
        typer.echo(
            "Error: Database URL must be provided via --database-url or DATABASE_URL env var.",
            err=True,
        )
        raise typer.Exit(code=1)

    if not username:
        typer.echo("Error: Username cannot be empty.", err=True)
        raise typer.Exit(code=1)

    if not email:
        typer.echo("Error: Email cannot be empty.", err=True)
        raise typer.Exit(code=1)

    if len(password) < 8:
        typer.echo("Error: Password must be at least 8 characters long.", err=True)
        raise typer.Exit(code=1)

    try:
        # Persistence logic
        # Use a synchronous engine for the CLI command
        # Ensure we don't pass async-specific driver if it's there
        sync_url = database_url
        if sync_url.startswith("sqlite+aiosqlite"):
            sync_url = sync_url.replace("sqlite+aiosqlite", "sqlite")

        engine = create_engine(sync_url)
        with Session(engine) as session:
            # Check for unique username
            existing_user = session.exec(select(User).where(User.username == username)).first()
            if existing_user:
                typer.echo(f"Error: User with username '{username}' already exists.", err=True)
                raise typer.Exit(code=1)

            # Create the superuser
            hashed_pwd = hash_password(password)
            user = User(
                username=username,
                email=email,
                password_hash=hashed_pwd,
                is_superuser=True,
            )
            session.add(user)
            session.commit()
            typer.echo(f"Superuser '{username}' created successfully!")
    except Exception as e:
        if isinstance(e, typer.Exit):
            raise
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
