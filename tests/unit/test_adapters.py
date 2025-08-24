import pytest
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from src.hyperadmin.core.adapters import BaseAdapter


def test_base_adapter_is_abstract():
    """
    Tests that BaseAdapter is an abstract class and cannot be instantiated.
    """
    with pytest.raises(TypeError):
        BaseAdapter()


def test_concrete_adapter_must_implement_all_methods():
    """
    Tests that a concrete implementation of BaseAdapter must implement all abstract methods.
    """

    class ConcreteAdapter(BaseAdapter):
        async def get(self, pk: Any) -> Any:
            pass

        async def list(
            self,
            page: int = 1,
            page_size: int = 10,
            search: str = None,
            filters: Dict[str, Any] = None,
            order_by: str = None,
        ) -> Tuple[List[Any], int]:
            pass

        async def create(self, data: Dict[str, Any]) -> Any:
            pass

        async def update(self, pk: Any, data: Dict[str, Any]) -> Any:
            pass

        async def delete(self, pk: Any) -> None:
            pass

        async def get_releated(self, pk: Any, field: str) -> List[Any]:
            pass

        async def get_schema(self) -> Dict[str, Any]:
            pass

    # This should not raise an error
    ConcreteAdapter()


def test_incomplete_adapter_raises_error():
    """
    Tests that a concrete implementation of BaseAdapter that misses some abstract methods
    raises a TypeError.
    """
    class IncompleteAdapter(BaseAdapter):
        async def get(self, pk: Any) -> Any:
            pass

    with pytest.raises(TypeError):
        IncompleteAdapter()
