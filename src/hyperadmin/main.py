from fastapi import APIRouter, FastAPI

from .views import ModelView


class Admin:
    """
    The main Admin class that holds the admin interface.
    """

    def __init__(self, app: FastAPI):
        self.app = app
        self.router = APIRouter()

    def register(self, model_view_class: type[ModelView]):
        """
        Registers a ModelView class with the admin interface.
        """
        view_instance = model_view_class()
        self.router.include_router(view_instance.router, tags=[view_instance.model.__name__])

    def mount(self, path: str):
        """
        Mounts the admin interface on the FastAPI application.
        """
        self.app.include_router(self.router, prefix=path, tags=["HyperAdmin"])
