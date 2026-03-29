"""Pipeline unit tests for the full select/multiselect widget flow (#173).

Tests the chain: classify_field → _pick_widget → widget → template rendering,
all with mock adapters and no real database.
"""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.core.choices import ChoiceItem, SelectFieldMeta
from hyperadmin.core.fields import classify_field
from hyperadmin.core.options import AdminOptions
from hyperadmin.views import dynamic as dynamic_module
from hyperadmin.views.forms import (
    MultiSelectWidget,
    PydanticForm,
    RelationMultiSelectWidget,
    RelationSelectWidget,
    SelectWidget,
)

if TYPE_CHECKING:
    import builtins


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PipelineModel(BaseModel):
    title: str
    priority: Priority
    priorities: list[Priority] = []
    tags: list[str] = []
    category_id: int | None = None
    is_active: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubAdapter(BaseAdapter):
    def __init__(self, model: Any) -> None:
        self.model = model
        rel = SimpleNamespace(
            key="category",
            local_columns=[SimpleNamespace(key="category_id", name="category_id")],
            uselist=False,
        )
        self.inspector = SimpleNamespace(relationships=[rel], c=[])

    async def get(self, pk: Any) -> Any:
        return None

    async def list(self, **kwargs: Any) -> tuple[list[Any], int]:
        return [], 0

    async def create(self, data: dict[str, Any]) -> Any:
        return SimpleNamespace(id=1, **data)

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        return SimpleNamespace(id=pk, **data)

    async def delete(self, pk: Any) -> None:
        pass

    async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
        return []

    async def get_schema(self) -> dict[str, Any]:
        return {}

    async def get_choices(
        self,
        field: str,
        q: str = "",
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> builtins.list[ChoiceItem]:
        return [
            ChoiceItem(value="1", label="Category A", selected=False),
            ChoiceItem(value="2", label="Category B", selected=False),
        ]

    async def save_inline_rows(self, spec: Any, rows: builtins.list[dict], parent_pk: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# 1. Enum → SelectWidget with correct choices
# ---------------------------------------------------------------------------


def test_enum_field_yields_select_widget() -> None:
    form = PydanticForm(PipelineModel)
    fields_by_name = {f.name: f for f in form.fields}
    w = fields_by_name["priority"].widget
    assert isinstance(w, SelectWidget)
    assert len(w.choices) == 3
    assert w.choices[0]["value"] == "low"
    assert w.choices[0]["label"] == "LOW"


# ---------------------------------------------------------------------------
# 2. list[Enum] → MultiSelectWidget with enum choices
# ---------------------------------------------------------------------------


def test_list_enum_field_yields_multiselect_widget() -> None:
    form = PydanticForm(PipelineModel)
    fields_by_name = {f.name: f for f in form.fields}
    w = fields_by_name["priorities"].widget
    assert isinstance(w, MultiSelectWidget)
    assert len(w.choices) == 3
    assert w.choices[2]["value"] == "high"


# ---------------------------------------------------------------------------
# 3. list[str] hybrid → MultiSelectWidget (empty choices)
# ---------------------------------------------------------------------------


def test_list_str_hybrid_yields_multiselect_widget() -> None:
    form = PydanticForm(PipelineModel)
    fields_by_name = {f.name: f for f in form.fields}
    w = fields_by_name["tags"].widget
    assert isinstance(w, MultiSelectWidget)
    assert w.choices == []


# ---------------------------------------------------------------------------
# 4. FK (mocked mapper) → RelationSelectWidget + preload=True
# ---------------------------------------------------------------------------


def test_fk_field_with_preload_gets_relation_select() -> None:
    """FK column detected via mapper → RelationSelectWidget with preload."""
    mock_col = MagicMock()
    mock_col.key = "category_id"
    mock_col.foreign_keys = {"fk"}

    mock_mapper = MagicMock()
    mock_mapper.relationships = []
    mock_mapper.columns = [mock_col]

    with (
        patch("hyperadmin.core.fields._HAS_SQLALCHEMY", True),
        patch("hyperadmin.core.fields.sa_inspect", return_value=mock_mapper, create=True),
    ):
        form = PydanticForm(PipelineModel, choices_base_url="/pipeline")
        fields_by_name = {f.name: f for f in form.fields}

    w = fields_by_name["category_id"].widget
    assert isinstance(w, RelationSelectWidget)
    assert w.preload is True
    assert w.choices_url == "/pipeline/category_id"


# ---------------------------------------------------------------------------
# 5. FK + preload=False → HTMX attrs present, no adapter call
# ---------------------------------------------------------------------------


def test_fk_relationship_yields_lazy_relation_select() -> None:
    """Relationship (not FK column) → preload=False → lazy HTMX widget."""
    mock_rel = MagicMock()
    mock_rel.key = "category_id"
    mock_rel.uselist = False

    mock_mapper = MagicMock()
    mock_mapper.relationships = [mock_rel]
    mock_mapper.columns = []

    with (
        patch("hyperadmin.core.fields._HAS_SQLALCHEMY", True),
        patch("hyperadmin.core.fields.sa_inspect", return_value=mock_mapper, create=True),
    ):
        form = PydanticForm(PipelineModel, choices_base_url="/pipeline")
        fields_by_name = {f.name: f for f in form.fields}

    w = fields_by_name["category_id"].widget
    assert isinstance(w, RelationSelectWidget)
    assert w.preload is False
    assert "/pipeline/category_id" in w.choices_url


# ---------------------------------------------------------------------------
# 6. M2M → RelationMultiSelectWidget
# ---------------------------------------------------------------------------


def test_m2m_relationship_yields_multiselect() -> None:
    """M2M (uselist=True) → RelationMultiSelectWidget."""

    class M2MModel(BaseModel):
        name: str
        categories: list[int] = []

    mock_rel = MagicMock()
    mock_rel.key = "categories"
    mock_rel.uselist = True

    mock_mapper = MagicMock()
    mock_mapper.relationships = [mock_rel]
    mock_mapper.columns = []

    with (
        patch("hyperadmin.core.fields._HAS_SQLALCHEMY", True),
        patch("hyperadmin.core.fields.sa_inspect", return_value=mock_mapper, create=True),
    ):
        form = PydanticForm(M2MModel, choices_base_url="/m2m")
        fields_by_name = {f.name: f for f in form.fields}

    w = fields_by_name["categories"].widget
    assert isinstance(w, RelationMultiSelectWidget)
    assert w.preload is False
    assert "/m2m/categories" in w.choices_url


# ---------------------------------------------------------------------------
# 7. Dependent select → hx-include attr
# ---------------------------------------------------------------------------


def test_dependent_select_renders_hx_include() -> None:
    """When dependent_on is set, the template should include hx-include attr."""
    from fastapi.templating import Jinja2Templates

    from hyperadmin.views.forms import FormField, RelationSelectWidget

    templates = Jinja2Templates(directory="src/hyperadmin/templates")
    widget = RelationSelectWidget(
        choices_url="/city/choices/state",
        preload=False,
        dependent_on="country_id",
    )
    field_info = MagicMock()
    field_info.is_required = False
    field_info.title = None
    field_info.description = None

    form_field = FormField(name="state_id", model_field=field_info, widget=widget)
    request = SimpleNamespace(url_for=lambda *a, **kw: "/")
    html = widget.render(templates, form_field, request)

    assert 'hx-include="[name=country_id]"' in html
    assert "change from:[name=country_id]" in html
    assert "Select country first" in html
    assert "ha-select--dependent" in html


# ---------------------------------------------------------------------------
# 8. Unchecked multiselect → empty list
# ---------------------------------------------------------------------------


def test_absent_multiselect_yields_empty_list() -> None:
    """_extract_form_data returns [] for absent multiselect fields."""

    class FakeFormData:
        def __init__(self, items: list[tuple[str, str]]) -> None:
            self._items = items

        def __iter__(self):
            seen: set[str] = set()
            for k, _v in self._items:
                if k not in seen:
                    seen.add(k)
                    yield k

        def __getitem__(self, key: str) -> str:
            for k, v in reversed(self._items):
                if k == key:
                    return v
            raise KeyError(key)

        def __contains__(self, key: str) -> bool:
            return any(k == key for k, _ in self._items)

        def keys(self):
            return list(dict(self._items).keys())

        def items(self):
            seen: set[str] = set()
            for k, v in self._items:
                if k not in seen:
                    seen.add(k)
                    yield k, v

        def getlist(self, key: str) -> list[str]:
            return [v for k, v in self._items if k == key]

    form = PydanticForm(
        PipelineModel,
        widgets={"tags": MultiSelectWidget(choices=[])},
    )
    _ = form.fields
    form_data = FakeFormData([("title", "Hello")])
    data = dynamic_module.DynamicModelView._extract_form_data(form_data, form)
    assert data["tags"] == []


# ---------------------------------------------------------------------------
# 9. choices_view: oversized limit → HTTP 400
# ---------------------------------------------------------------------------


@pytest.fixture
def view():
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="src/hyperadmin/templates")
    adapter = StubAdapter(PipelineModel)
    options = AdminOptions()
    return dynamic_module.DynamicModelView(
        adapter=adapter,
        options=options,
        templates=templates,
        app_label=None,
    )


@pytest.mark.anyio
async def test_choices_view_rejects_oversized_limit(view: dynamic_module.DynamicModelView) -> None:
    from fastapi import HTTPException

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"q=&limit=999&offset=0",
        "headers": [],
        "app": SimpleNamespace(
            url_path_for=lambda name, **kw: SimpleNamespace(
                make_absolute_url=lambda base_url=None, **kwargs: f"/{name}"
            )
        ),
    }
    from starlette.requests import Request

    request = Request(scope)
    with pytest.raises(HTTPException) as exc_info:
        await view.choices_view(request, field_name="category", q="", limit=999, offset=0)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# 10. choices_view: unknown field → HTTP 404
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_choices_view_unknown_field_404(view: dynamic_module.DynamicModelView) -> None:
    from fastapi import HTTPException
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"q=&limit=50&offset=0",
        "headers": [],
        "app": SimpleNamespace(
            url_path_for=lambda name, **kw: SimpleNamespace(
                make_absolute_url=lambda base_url=None, **kwargs: f"/{name}"
            )
        ),
    }
    request = Request(scope)
    with pytest.raises(HTTPException) as exc_info:
        await view.choices_view(request, field_name="nonexistent", q="", limit=50, offset=0)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 11. classify_field roundtrip: all types
# ---------------------------------------------------------------------------


def test_classify_field_roundtrip_enum_single() -> None:
    fi = PipelineModel.model_fields["priority"]
    meta = classify_field(fi, PipelineModel)
    assert meta is not None
    assert meta.choices_source == "enum"
    assert meta.multiple is False


def test_classify_field_roundtrip_enum_list() -> None:
    fi = PipelineModel.model_fields["priorities"]
    meta = classify_field(fi, PipelineModel)
    assert meta is not None
    assert meta.choices_source == "enum"
    assert meta.multiple is True


def test_classify_field_roundtrip_static_list() -> None:
    fi = PipelineModel.model_fields["tags"]
    meta = classify_field(fi, PipelineModel)
    assert meta is not None
    assert meta.choices_source == "static"
    assert meta.multiple is True


def test_classify_field_roundtrip_plain_str_none() -> None:
    fi = PipelineModel.model_fields["title"]
    assert classify_field(fi, PipelineModel) is None


# ---------------------------------------------------------------------------
# 12. _build_relation_widgets preload: adapter called, choices injected
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_build_relation_widgets_preload_injects_choices(
    view: dynamic_module.DynamicModelView,
) -> None:
    """When preload=True, _build_relation_widgets calls adapter.get_choices and injects choices."""
    with patch("hyperadmin.views.dynamic.classify_field") as mock_classify:
        mock_classify.return_value = SelectFieldMeta(
            choices_source="relation", preload=True, multiple=False
        )
        widgets = await view._build_relation_widgets(
            field_names=["category_id"], selected_values={"category_id": "1"}
        )
    assert "category_id" in widgets
    w = widgets["category_id"]
    assert isinstance(w, RelationSelectWidget)
    assert w.preload is True
    assert len(w.choices) == 2
    # First choice should be marked selected (value="1" matches selected_values)
    assert w.choices[0]["selected"] is True
    assert w.choices[1]["selected"] is False


# ---------------------------------------------------------------------------
# 13. _build_relation_widgets lazy: no adapter call, empty choices
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_build_relation_widgets_lazy_no_adapter_call(
    view: dynamic_module.DynamicModelView,
) -> None:
    """When preload=False, adapter.get_choices is NOT called; choices are empty."""
    view.adapter.get_choices = AsyncMock(return_value=[])
    with patch("hyperadmin.views.dynamic.classify_field") as mock_classify:
        mock_classify.return_value = SelectFieldMeta(
            choices_source="relation", preload=False, multiple=False
        )
        widgets = await view._build_relation_widgets(field_names=["category_id"])
    assert "category_id" in widgets
    w = widgets["category_id"]
    assert isinstance(w, RelationSelectWidget)
    assert w.preload is False
    assert w.choices == []
    view.adapter.get_choices.assert_not_awaited()


# ---------------------------------------------------------------------------
# 14. Template rendering: enum select renders correct <option> markup
# ---------------------------------------------------------------------------


def test_select_widget_template_renders_options() -> None:
    from fastapi.templating import Jinja2Templates

    from hyperadmin.views.forms import FormField

    templates = Jinja2Templates(directory="src/hyperadmin/templates")
    choices = [
        ChoiceItem(value="low", label="LOW", selected=False),
        ChoiceItem(value="high", label="HIGH", selected=True),
    ]
    widget = SelectWidget(choices=choices)
    field_info = MagicMock()
    field_info.is_required = True
    field_info.title = "Priority"
    field_info.description = None
    form_field = FormField(name="priority", model_field=field_info, widget=widget)
    request = SimpleNamespace(url_for=lambda *a, **kw: "/")
    html = widget.render(templates, form_field, request)

    assert '<option value="low">' in html
    # Template whitespace stripping may omit space before "selected"
    assert "high" in html
    assert "selected" in html
    assert "Priority" in html


# ---------------------------------------------------------------------------
# 15. Hybrid field coercion: round-trip JSON and CSV
# ---------------------------------------------------------------------------


def test_hybrid_json_roundtrip() -> None:
    from hyperadmin.views.forms import hybrid_to_python, hybrid_to_storage

    original = ["python", "fastapi", "htmx"]
    stored = hybrid_to_storage(original, "json")
    assert stored == '["python", "fastapi", "htmx"]'
    restored = hybrid_to_python(stored, "json")
    assert restored == original


def test_hybrid_csv_roundtrip() -> None:
    from hyperadmin.views.forms import hybrid_to_python, hybrid_to_storage

    original = ["python", "fastapi", "htmx"]
    stored = hybrid_to_storage(original, "csv")
    assert stored == "python,fastapi,htmx"
    restored = hybrid_to_python(stored, "csv")
    assert restored == original


def test_hybrid_to_python_empty_string() -> None:
    from hyperadmin.views.forms import hybrid_to_python

    assert hybrid_to_python("", "json") == []
    assert hybrid_to_python("", "csv") == []


def test_hybrid_to_python_list_passthrough() -> None:
    from hyperadmin.views.forms import hybrid_to_python

    assert hybrid_to_python(["a", "b"], "json") == ["a", "b"]
