from typing import Any

import pytest

from hyperadmin.core.choices import ChoiceItem, ChoicesProvider, SelectFieldMeta


def test_choice_item_shape():
    item: ChoiceItem = {"value": "1", "label": "One", "selected": False}
    assert item["value"] == "1"
    assert item["label"] == "One"
    assert item["selected"] is False


def test_select_field_meta_defaults():
    meta = SelectFieldMeta(choices_source="enum")
    assert meta.choices_source == "enum"
    assert meta.preload is True
    assert meta.multiple is False
    assert meta.searchable is False
    assert meta.dependent_on is None


def test_select_field_meta_custom():
    meta = SelectFieldMeta(
        choices_source="relation",
        preload=False,
        multiple=True,
        searchable=True,
        dependent_on="other_field",
    )
    assert meta.choices_source == "relation"
    assert meta.preload is False
    assert meta.multiple is True
    assert meta.searchable is True
    assert meta.dependent_on == "other_field"


class MockChoicesProvider:
    async def get_choices(
        self,
        field: str,
        q: str = "",
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> list[ChoiceItem]:
        return [{"value": "mock", "label": "Mock", "selected": False}]


@pytest.mark.anyio
async def test_choices_provider_protocol():
    provider: ChoicesProvider = MockChoicesProvider()
    choices = await provider.get_choices("test_field")
    assert len(choices) == 1
    assert choices[0]["value"] == "mock"
