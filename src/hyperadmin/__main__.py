import typer

from hyperadmin.management.commands.createsuperuser import app as createsuperuser_app
from hyperadmin.management.commands.seed import app as seed_app

app = typer.Typer(help="HyperAdmin management CLI.")
app.add_typer(createsuperuser_app)
app.add_typer(seed_app)

if __name__ == "__main__":
    app()
