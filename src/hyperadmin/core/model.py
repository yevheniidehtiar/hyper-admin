"""This module will contain the base HyperAdminModel class."""

import abc
import sys
from typing import Any

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from pydantic import BaseModel


class HyperAdminModel(BaseModel, abc.ABC):
    """A base class for creating administrative models in HyperAdmin.

    This class provides the core functionality for integrating Pydantic models
    with the HyperAdmin interface. It serves as a foundation for defining
    how models are displayed, validated, and managed in the admin panel.

    It includes abstract methods for CRUD operations and placeholder methods
    for lifecycle hooks, which should be implemented by subclasses.
    """

    class Meta:
        """Inner class for model-specific configuration.

        This class allows for the customization of the admin behavior for each
        model, such as specifying the list of fields to display or defining
        custom actions.
        """

    @classmethod
    @abc.abstractmethod
    async def create(cls, data: dict[str, Any]) -> Self:
        """Creates a new model instance."""
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    async def get(cls, pk: Any) -> Self | None:
        """Retrieves a model instance by its primary key."""
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, data: dict[str, Any]) -> None:
        """Updates the model instance."""
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self) -> None:
        """Deletes the model instance."""
        raise NotImplementedError

    async def before_save(self) -> None:
        """Lifecycle hook called before saving the model."""

    async def after_save(self) -> None:
        """Lifecycle hook called after saving the model."""

    async def before_delete(self) -> None:
        """Lifecycle hook called before deleting the model."""

    async def after_delete(self) -> None:
        """Lifecycle hook called after deleting the model."""
