"""Tests for the enhanced list view functionality."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Field, SQLModel

from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.core.options import AdminOptions
from hyperadmin.views.dynamic import DynamicModelView


class SampleModel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int


class MockAdapter(BaseAdapter):
    """Mock adapter for testing."""

    def __init__(self, model, engine):
        super().__init__(model, engine)

    async def get(self, pk):
        return None

    async def list(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: dict | None = None,
        order_by: str | None = None,
    ):
        # Mock data for testing
        mock_items = [
            SampleModel(id=1, name="Alice", email="alice@example.com", age=25),
            SampleModel(id=2, name="Bob", email="bob@example.com", age=30),
            SampleModel(id=3, name="Charlie", email="charlie@example.com", age=35),
        ]

        # Apply search filtering if provided
        if search:
            filtered_items = [
                item
                for item in mock_items
                if search.lower() in item.name.lower() or search.lower() in item.email.lower()
            ]
            mock_items = filtered_items

        total_count = len(mock_items)

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = mock_items[start_idx:end_idx]

        return paginated_items, total_count

    async def create(self, data):
        return SampleModel(**data)

    async def update(self, pk, data):
        return SampleModel(id=pk, **data)

    async def delete(self, pk):
        return None

    async def get_related(self, pk, field):
        return []

    async def get_schema(self):
        return SampleModel.model_json_schema()


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.headers = {}
    return request


@pytest.fixture
def mock_htmx_request():
    """Create a mock HTMX request."""
    request = MagicMock(spec=Request)
    request.headers = {"hx-request": "true"}
    return request


@pytest.fixture
def mock_templates():
    """Create a mock Jinja2Templates."""
    templates = MagicMock(spec=Jinja2Templates)
    templates.TemplateResponse = MagicMock(return_value="mocked_response")
    # Mock the env attribute for template resolution
    templates.env = MagicMock()
    templates.env.loader = None  # Simplify template resolution
    return templates


@pytest.fixture
def view_instance(mock_templates):
    """Create a DynamicModelView instance with mock dependencies."""
    adapter = MockAdapter(SampleModel, None)
    options = AdminOptions()
    view = DynamicModelView(
        adapter=adapter, options=options, templates=mock_templates, app_label="test"
    )
    # Mock the _get_template_name method to return predictable results
    view._get_template_name = MagicMock(side_effect=lambda name: f"{name}.html")
    return view


async def test_list_view_basic(view_instance, mock_request, mock_templates, anyio_backend):
    """Test basic list view functionality."""
    result = await view_instance.list_view(
        request=mock_request, page=1, page_size=10, search="", sort_by=None, sort_direction="asc"
    )

    # Check that TemplateResponse was called
    mock_templates.TemplateResponse.assert_called_once()

    # Get the context passed to the template
    call_args = mock_templates.TemplateResponse.call_args
    template_name = call_args[0][0]
    context = call_args[0][1]

    # Verify template name
    assert template_name.endswith("list.html")

    # Verify context structure
    assert context["model_name"] == "SampleModel"
    assert context["fields"] == ["id", "name", "email", "age"]
    assert len(context["items"]) == 3
    assert context["pagination"]["total_items"] == 3
    assert context["pagination"]["page"] == 1
    assert context["pagination"]["page_size"] == 10


async def test_list_view_with_pagination(
    view_instance, mock_request, mock_templates, anyio_backend
):
    """Test list view with pagination parameters."""
    result = await view_instance.list_view(
        request=mock_request, page=2, page_size=2, search="", sort_by=None, sort_direction="asc"
    )

    # Get the context
    call_args = mock_templates.TemplateResponse.call_args
    context = call_args[0][1]

    # Verify pagination context
    assert context["pagination"]["page"] == 2
    assert context["pagination"]["page_size"] == 2
    assert context["pagination"]["total_pages"] == 2  # 3 items / 2 per page = 2 pages
    assert context["pagination"]["start_index"] == 3  # Second page starts at item 3
    assert context["pagination"]["end_index"] == 3  # Only 1 item on second page


async def test_list_view_with_search(view_instance, mock_request, mock_templates, anyio_backend):
    """Test list view with search functionality."""
    result = await view_instance.list_view(
        request=mock_request,
        page=1,
        page_size=10,
        search="alice",
        sort_by=None,
        sort_direction="asc",
    )

    # Get the context
    call_args = mock_templates.TemplateResponse.call_args
    context = call_args[0][1]

    # Verify search results
    assert context["search_query"] == "alice"
    assert len(context["items"]) == 1
    assert context["items"][0].name == "Alice"
    assert context["pagination"]["total_items"] == 1


async def test_list_view_with_sorting(view_instance, mock_request, mock_templates, anyio_backend):
    """Test list view with sorting parameters."""
    result = await view_instance.list_view(
        request=mock_request, page=1, page_size=10, search="", sort_by="name", sort_direction="desc"
    )

    # Get the context
    call_args = mock_templates.TemplateResponse.call_args
    context = call_args[0][1]

    # Verify sorting context
    assert context["sort_by"] == "name"
    assert context["sort_direction"] == "desc"


async def test_list_view_htmx_request(
    view_instance, mock_htmx_request, mock_templates, anyio_backend
):
    """Test that HTMX requests use the table component template."""
    result = await view_instance.list_view(
        request=mock_htmx_request,
        page=1,
        page_size=10,
        search="",
        sort_by=None,
        sort_direction="asc",
    )

    # Get the template name used
    call_args = mock_templates.TemplateResponse.call_args
    template_name = call_args[0][0]

    # Verify HTMX requests use table component
    assert template_name == "components/table.html"


async def test_list_view_default_sort_column(
    view_instance, mock_request, mock_templates, anyio_backend
):
    """Test that default sort column is set when none provided."""
    result = await view_instance.list_view(
        request=mock_request, page=1, page_size=10, search="", sort_by=None, sort_direction="asc"
    )

    # Get the context
    call_args = mock_templates.TemplateResponse.call_args
    context = call_args[0][1]

    # Should default to first field (id)
    assert context["sort_by"] == "id"


async def test_list_view_error_handling(view_instance, mock_request, mock_templates, anyio_backend):
    """Test error handling when adapter fails."""
    # Mock adapter to raise an exception
    view_instance.adapter.list = AsyncMock(side_effect=Exception("Database error"))

    result = await view_instance.list_view(
        request=mock_request, page=1, page_size=10, search="", sort_by=None, sort_direction="asc"
    )

    # Get the context
    call_args = mock_templates.TemplateResponse.call_args
    context = call_args[0][1]

    # Should handle error gracefully
    assert context["items"] == []
    assert context["pagination"]["total_items"] == 0
    assert context["pagination"]["total_pages"] == 0


async def test_list_view_empty_results(view_instance, mock_request, mock_templates, anyio_backend):
    """Test list view with no results."""
    # Mock adapter to return empty results
    view_instance.adapter.list = AsyncMock(return_value=([], 0))

    result = await view_instance.list_view(
        request=mock_request, page=1, page_size=10, search="", sort_by=None, sort_direction="asc"
    )

    # Get the context
    call_args = mock_templates.TemplateResponse.call_args
    context = call_args[0][1]

    # Verify empty results are handled correctly
    assert context["items"] == []
    assert context["pagination"]["total_items"] == 0
    assert context["pagination"]["start_index"] == 0
    assert context["pagination"]["end_index"] == 0


async def test_list_view_parameter_validation(
    view_instance, mock_request, mock_templates, anyio_backend
):
    """Test that parameters are passed correctly to the adapter."""
    # Mock the adapter to capture the parameters
    mock_list = AsyncMock(return_value=([], 0))
    view_instance.adapter.list = mock_list

    await view_instance.list_view(
        request=mock_request,
        page=2,
        page_size=5,
        search="test",
        sort_by="name",
        sort_direction="desc",
    )

    # Verify adapter was called with correct parameters
    mock_list.assert_called_once_with(
        page=2,
        page_size=5,
        search="test",
        order_by="-name",  # Should be prefixed with - for desc
    )
