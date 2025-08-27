import pytest
from pydantic import ValidationError

from hyperadmin.core.model import HyperAdminModel


class ConcreteAdminModel(HyperAdminModel):
    name: str
    value: int

    @classmethod
    async def create(cls, data):
        return cls(**data)

    @classmethod
    async def get(cls, pk):
        return None

    async def update(self, data):
        pass

    async def delete(self):
        pass


def test_hyper_admin_model_instantiation():
    """Tests that a concrete implementation of HyperAdminModel can be instantiated."""
    model = ConcreteAdminModel(name="test", value=123)
    assert model.name == "test"
    assert model.value == 123


def test_hyper_admin_model_is_abstract():
    """Tests that the base HyperAdminModel cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class HyperAdminModel"):
        HyperAdminModel()


def test_hyper_admin_model_pydantic_validation():
    """Tests that Pydantic validation is active."""
    with pytest.raises(ValidationError):
        ConcreteAdminModel(name="test", value="not an int")
