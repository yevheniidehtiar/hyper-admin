from fastapi import APIRouter, FastAPI
from sqlmodel import SQLModel

from hyperadmin.views import ModelView


class Admin:
    """The main Admin class that holds the admin interface."""

    def __init__(
        self,
        app: FastAPI,
        engine: "Engine",
        title: str = "HyperAdmin",
        base_url: str = "/admin",
    ):
        self.app = app
        self.engine = engine
        self.title = title
        self.base_url = base_url
        self.router = APIRouter()
        self.app.include_router(self.router, prefix=base_url)

    def add_view(self, view: type[ModelView]) -> None:
        """
        Registers a ModelView class with the admin interface.
        """
        view_instance = view()
        self.router.include_router(
            view_instance.router,
            prefix=f"/{view_instance.model.__name__.lower()}",
            tags=[view_instance.model.__name__],
        )
