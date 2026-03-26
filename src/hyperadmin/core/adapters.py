import builtins
from abc import ABC, abstractmethod
from typing import Any

from hyperadmin.core.choices import ChoiceItem


class BaseAdapter(ABC):
    """Abstract base class for data adapters.

    Defines the contract for all data operations (get, list, create, update, delete).
    Subclass this to add support for a new ORM or data source.

    Example:
        ```python
        class MyAdapter(BaseAdapter):
            async def get(self, pk): ...
        ```
    """

    model: Any

    def __init__(self, model: Any, engine: Any) -> None:
        self.model = model
        self.engine = engine

    @abstractmethod
    async def get(self, pk: Any) -> Any:
        """
        Retrieves a single object by its primary key.

        Args:
            pk: The primary key of the object to retrieve.

        Returns:
            The retrieved object, or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    async def list(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
    ) -> tuple[list[Any], int]:
        """
        Retrieves a list of objects with optional pagination, searching, and filtering.

        Args:
            page: The page number for pagination.
            page_size: The number of items per page.
            search: A search query to filter the results.
            filters: A dictionary of filters to apply to the query.
            order_by: The field to order the results by.

        Returns:
            A tuple containing the list of objects and the total count of objects.
        """
        raise NotImplementedError

    @abstractmethod
    async def create(self, data: dict[str, Any]) -> Any:
        """
        Creates a new object.

        Args:
            data: A dictionary of data for the new object.

        Returns:
            The created object.
        """
        raise NotImplementedError

    @abstractmethod
    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        """
        Updates an existing object.

        Args:
            pk: The primary key of the object to update.
            data: A dictionary of data to update the object with.

        Returns:
            The updated object.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, pk: Any) -> None:
        """
        Deletes an object by its primary key.

        Args:
            pk: The primary key of the object to delete.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
        """
        Retrieves related objects for a given object and field.

        Args:
            pk: The primary key of the object.
            field: The name of the relationship field.

        Returns:
            A list of related objects.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_schema(self) -> dict[str, Any]:
        """
        Retrieves the schema definition for the model.

        Returns:
            A dictionary representing the model's schema.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_choices(
        self,
        field: str,
        q: str = "",
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> builtins.list[ChoiceItem]:
        """Return paginated, searchable choices for a relation field.

        Args:
            field: The relation field name on this adapter's model.
            q: Optional search string (ILIKE match on string columns).
            limit: Max results to return. Must not exceed 200.
            offset: Number of rows to skip for pagination.
            **filters: Extra equality filters forwarded to the query (cascading support).

        Returns:
            A list of ``ChoiceItem`` dicts with ``value``, ``label``, ``selected=False``.

        Raises:
            ValueError: When ``limit`` exceeds 200.
        """
        raise NotImplementedError
