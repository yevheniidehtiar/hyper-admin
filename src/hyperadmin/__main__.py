import typer

from hyperadmin.management.commands.createsuperuser import app as createsuperuser_app
from hyperadmin.management.commands.initdb import app as initdb_app
from hyperadmin.management.commands.seed import app as seed_app

app = typer.Typer(
    help="HyperAdmin management CLI.",
    # Governs sub-typers added via add_typer (e.g. init-db, createsuperuser):
    # never print frame locals (which include --database-url / --password)
    # in a pretty traceback. See initdb.py for the full rationale.
    pretty_exceptions_show_locals=False,
)
app.add_typer(createsuperuser_app)
app.add_typer(initdb_app)
app.add_typer(seed_app)

if __name__ == "__main__":
    app()
