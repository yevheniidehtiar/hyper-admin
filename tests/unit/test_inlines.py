"""Unit tests for inline model editing (InlineModelSpec, InlineFormset)."""

from __future__ import annotations

from unittest.mock import MagicMock

from pydantic import BaseModel

from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.options import AdminOptions
from hyperadmin.views.forms import InlineFormRow, InlineFormset

# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class ParentModel(BaseModel):
    id: int | None = None
    name: str = ""


class ChildModel(BaseModel):
    id: int | None = None
    parent_id: int | None = None
    description: str = ""
    quantity: int = 1


class ItemModel(BaseModel):
    id: int | None = None
    order_id: int | None = None
    product: str = ""
    price: float = 0.0
    notes: str | None = None


# ---------------------------------------------------------------------------
# InlineModelSpec
# ---------------------------------------------------------------------------


class TestInlineModelSpec:
    def test_defaults(self) -> None:
        spec = InlineModelSpec(model=ChildModel, fk_field="parent_id")
        assert spec.fk_field == "parent_id"
        assert spec.fields == []
        assert spec.max_num == 0
        assert spec.extra == 1
        assert spec.title == "ChildModels"

    def test_custom_title(self) -> None:
        spec = InlineModelSpec(model=ChildModel, fk_field="parent_id", title="Children")
        assert spec.title == "Children"

    def test_model_name(self) -> None:
        spec = InlineModelSpec(model=ChildModel, fk_field="parent_id")
        assert spec.model_name == "childmodel"

    def test_get_display_fields_explicit(self) -> None:
        spec = InlineModelSpec(
            model=ChildModel,
            fk_field="parent_id",
            fields=["description", "quantity"],
        )
        assert spec.get_display_fields() == ["description", "quantity"]

    def test_get_display_fields_auto(self) -> None:
        spec = InlineModelSpec(model=ChildModel, fk_field="parent_id")
        fields = spec.get_display_fields()
        assert "description" in fields
        assert "quantity" in fields
        assert "id" not in fields
        assert "parent_id" not in fields


# ---------------------------------------------------------------------------
# AdminOptions.inlines
# ---------------------------------------------------------------------------


class TestAdminOptionsInlines:
    def test_default_empty(self) -> None:
        opts = AdminOptions()
        assert opts.inlines == []

    def test_with_inlines(self) -> None:
        spec = InlineModelSpec(model=ChildModel, fk_field="parent_id")
        opts = AdminOptions(inlines=[spec])
        assert len(opts.inlines) == 1
        assert opts.inlines[0].model is ChildModel

    def test_multiple_inlines(self) -> None:
        opts = AdminOptions(
            inlines=[
                InlineModelSpec(model=ChildModel, fk_field="parent_id"),
                InlineModelSpec(model=ItemModel, fk_field="order_id"),
            ]
        )
        assert len(opts.inlines) == 2


# ---------------------------------------------------------------------------
# InlineFormset
# ---------------------------------------------------------------------------


class TestInlineFormset:
    def _make_formset(self, **kwargs) -> InlineFormset:
        spec = InlineModelSpec(model=ChildModel, fk_field="parent_id", **kwargs)
        return InlineFormset(spec=spec)

    def test_prefix(self) -> None:
        fs = self._make_formset()
        assert fs.prefix == "childmodel"

    def test_display_fields(self) -> None:
        fs = self._make_formset()
        assert "description" in fs.display_fields
        assert "quantity" in fs.display_fields

    def test_field_labels(self) -> None:
        fs = self._make_formset()
        labels = fs.field_labels
        assert "Description" in labels
        assert "Quantity" in labels

    def test_build_empty_rows(self) -> None:
        fs = self._make_formset(extra=3)
        fs.build_empty_rows()
        assert len(fs.rows) == 3
        for row in fs.rows:
            assert isinstance(row, InlineFormRow)
            assert row.pk is None
            assert len(row.fields) > 0

    def test_build_empty_rows_custom_count(self) -> None:
        fs = self._make_formset(extra=1)
        fs.build_empty_rows(count=5)
        assert len(fs.rows) == 5

    def test_populate_from_instances(self) -> None:
        fs = self._make_formset(extra=2)
        instances = [
            ChildModel(id=10, parent_id=1, description="A", quantity=5),
            ChildModel(id=20, parent_id=1, description="B", quantity=3),
        ]
        fs.populate_from_instances(instances)
        # 2 existing + 2 extra
        assert len(fs.rows) == 4
        assert fs.rows[0].pk == 10
        assert fs.rows[1].pk == 20
        assert fs.rows[2].pk is None
        assert fs.rows[3].pk is None
        # Verify field values from first existing row
        desc_field = next(f for f in fs.rows[0].fields if f.name == "description")
        assert desc_field.value == "A"

    def test_extract_submitted_data_basic(self) -> None:
        fs = self._make_formset()
        form_data = MagicMock()
        form_data.__iter__ = MagicMock(
            return_value=iter(
                [
                    "childmodel-0-description",
                    "childmodel-0-quantity",
                    "childmodel-0-DELETE",
                ]
            )
        )
        form_data.get = lambda key, default="": {
            "childmodel-0-description": "Test item",
            "childmodel-0-quantity": "5",
            "childmodel-0-DELETE": "",
        }.get(key, default)

        rows = fs.extract_submitted_data(form_data)
        assert len(rows) == 1
        assert rows[0]["description"] == "Test item"
        assert rows[0]["quantity"] == "5"

    def test_extract_submitted_data_with_delete(self) -> None:
        fs = self._make_formset()
        form_data = MagicMock()
        form_data.__iter__ = MagicMock(
            return_value=iter(
                [
                    "childmodel-0-description",
                    "childmodel-0-quantity",
                    "childmodel-0-pk",
                    "childmodel-0-DELETE",
                ]
            )
        )
        form_data.get = lambda key, default="": {
            "childmodel-0-description": "Old item",
            "childmodel-0-quantity": "1",
            "childmodel-0-pk": "42",
            "childmodel-0-DELETE": "1",
        }.get(key, default)

        rows = fs.extract_submitted_data(form_data)
        assert len(rows) == 1
        assert rows[0]["_delete"] is True
        assert rows[0]["_pk"] == 42

    def test_extract_submitted_data_skips_empty_rows(self) -> None:
        fs = self._make_formset()
        form_data = MagicMock()
        form_data.__iter__ = MagicMock(
            return_value=iter(
                [
                    "childmodel-0-description",
                    "childmodel-0-quantity",
                    "childmodel-0-DELETE",
                    "childmodel-1-description",
                    "childmodel-1-quantity",
                    "childmodel-1-DELETE",
                ]
            )
        )
        form_data.get = lambda key, default="": {
            "childmodel-0-description": "Real",
            "childmodel-0-quantity": "3",
            "childmodel-0-DELETE": "",
            "childmodel-1-description": "",
            "childmodel-1-quantity": "",
            "childmodel-1-DELETE": "",
        }.get(key, default)

        rows = fs.extract_submitted_data(form_data)
        assert len(rows) == 1
        assert rows[0]["description"] == "Real"

    def test_validate_rows_success(self) -> None:
        fs = self._make_formset()
        rows_data = [{"description": "Valid", "quantity": "5"}]
        valid, errors = fs.validate_rows(rows_data, parent_pk=1)
        assert len(valid) == 1
        assert errors == {}
        assert valid[0]["description"] == "Valid"
        assert valid[0]["quantity"] == 5
        assert valid[0]["parent_id"] == 1

    def test_validate_rows_with_errors(self) -> None:
        fs = self._make_formset()
        # quantity must be int, "abc" should fail
        rows_data = [{"description": "Bad", "quantity": "abc"}]
        valid, errors = fs.validate_rows(rows_data, parent_pk=1)
        assert len(valid) == 0
        assert 0 in errors
        assert "quantity" in errors[0]

    def test_validate_rows_preserves_pk(self) -> None:
        fs = self._make_formset()
        rows_data = [{"_pk": 42, "description": "Updated", "quantity": "10"}]
        valid, _errors = fs.validate_rows(rows_data, parent_pk=1)
        assert len(valid) == 1
        assert valid[0]["_pk"] == 42

    def test_validate_rows_delete(self) -> None:
        fs = self._make_formset()
        rows_data = [{"_delete": True, "_pk": 99}]
        valid, _errors = fs.validate_rows(rows_data)
        assert len(valid) == 1
        assert valid[0]["_delete"] is True
        assert valid[0]["_pk"] == 99

    def test_rebuild_from_submitted(self) -> None:
        fs = self._make_formset()
        form_data = MagicMock()
        form_data.__iter__ = MagicMock(
            return_value=iter(
                [
                    "childmodel-0-description",
                    "childmodel-0-quantity",
                    "childmodel-0-pk",
                    "childmodel-0-DELETE",
                ]
            )
        )
        form_data.get = lambda key, default="": {
            "childmodel-0-description": "Re-rendered",
            "childmodel-0-quantity": "7",
            "childmodel-0-pk": "5",
            "childmodel-0-DELETE": "",
        }.get(key, default)

        fs.rebuild_from_submitted(form_data)
        assert len(fs.rows) == 1
        assert fs.rows[0].pk == 5
        desc = next(f for f in fs.rows[0].fields if f.name == "description")
        assert desc.value == "Re-rendered"

    def test_rebuild_applies_errors(self) -> None:
        fs = self._make_formset()
        fs.errors = {0: {"quantity": ["Invalid value"]}}
        form_data = MagicMock()
        form_data.__iter__ = MagicMock(
            return_value=iter(
                [
                    "childmodel-0-description",
                    "childmodel-0-quantity",
                    "childmodel-0-DELETE",
                ]
            )
        )
        form_data.get = lambda key, default="": {
            "childmodel-0-description": "Test",
            "childmodel-0-quantity": "bad",
            "childmodel-0-DELETE": "",
        }.get(key, default)

        fs.rebuild_from_submitted(form_data)
        qty_field = next(f for f in fs.rows[0].fields if f.name == "quantity")
        assert qty_field.errors == ["Invalid value"]


# ---------------------------------------------------------------------------
# InlineFormRow
# ---------------------------------------------------------------------------


class TestInlineFormRow:
    def test_row_defaults(self) -> None:
        row = InlineFormRow(index=0, fields=[])
        assert row.index == 0
        assert row.pk is None
        assert row.delete is False

    def test_row_with_pk(self) -> None:
        row = InlineFormRow(index=1, fields=[], pk=42)
        assert row.pk == 42


# ---------------------------------------------------------------------------
# InlineFormset with ItemModel (optional fields)
# ---------------------------------------------------------------------------


class TestInlineFormsetOptionalFields:
    def test_optional_field_empty_string_becomes_none(self) -> None:
        spec = InlineModelSpec(model=ItemModel, fk_field="order_id")
        fs = InlineFormset(spec=spec)
        rows_data = [{"product": "Widget", "price": "9.99", "notes": ""}]
        valid, errors = fs.validate_rows(rows_data, parent_pk=1)
        assert len(valid) == 1
        assert errors == {}
        assert valid[0]["notes"] is None

    def test_display_fields_exclude_fk_and_id(self) -> None:
        spec = InlineModelSpec(model=ItemModel, fk_field="order_id")
        fs = InlineFormset(spec=spec)
        fields = fs.display_fields
        assert "id" not in fields
        assert "order_id" not in fields
        assert "product" in fields
        assert "price" in fields
        assert "notes" in fields
