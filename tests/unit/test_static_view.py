from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.exceptions import HTTPException

from hyperadmin.views.static import ModelView, templates


class MockModel:
    __name__ = "MockModel"
    id: int
    name: str
    model_fields = {"id": int, "name": str}

    def model_dump(self):
        return {"id": self.id, "name": self.name}


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.model = MockModel
    adapter.list = AsyncMock(return_value=([{"id": 1, "name": "Test"}], 1))
    adapter.get = AsyncMock(return_value={"id": 1, "name": "Test"})
    adapter.create = AsyncMock()
    adapter.update = AsyncMock()
    adapter.delete = AsyncMock()
    return adapter


@pytest.fixture
def model_view(mock_adapter):
    with patch.object(templates, "TemplateResponse", new=MagicMock()) as mock_template_response:
        view = ModelView(adapter=mock_adapter)
        view.templates = templates
        yield view, mock_template_response


@pytest.mark.anyio
async def test_list_view(model_view, mock_adapter):
    view, mock_template_response = model_view
    request = Request({"type": "http", "method": "GET", "path": "/"})
    await view.list_view(request)
    mock_template_response.assert_called_with(
        "list.html",
        {
            "request": request,
            "model_name": "MockModel",
            "fields": ["id", "name"],
            "items": ([{"id": 1, "name": "Test"}], 1)[0],
        },
    )


@pytest.mark.anyio
async def test_detail_view_found(model_view, mock_adapter):
    view, mock_template_response = model_view
    request = Request({"type": "http", "method": "GET", "path": "/1"})
    item = MockModel()
    item.id = 1
    item.name = "Test"
    mock_adapter.get.return_value = item
    await view.detail_view(request, item_id=1)
    mock_template_response.assert_called_with(
        "detail.html",
        {
            "request": request,
            "item_name": "MockModel #1",
            "item": {"id": 1, "name": "Test"},
        },
    )


@pytest.mark.anyio
async def test_detail_view_not_found(model_view, mock_adapter):
    view, _ = model_view
    request = Request({"type": "http", "method": "GET", "path": "/1"})
    mock_adapter.get.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await view.detail_view(request, item_id=1)
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_create_view_get(model_view):
    view, mock_template_response = model_view
    request = Request({"type": "http", "method": "GET", "path": "/create"})
    await view.create_view(request)
    mock_template_response.assert_called_with(
        "create.html",
        {
            "request": request,
            "model_name": "MockModel",
            "fields": ["id", "name"],
        },
    )


@pytest.mark.anyio
async def test_create_view_post(model_view, mock_adapter):
    view, _ = model_view

    async def form():
        return {"name": "New Test"}

    request = Request({"type": "http", "method": "POST", "path": "/create"})
    request.form = form
    response = await view.create_view(request)
    assert response == {"message": "Item created successfully"}
    mock_adapter.create.assert_called_once_with(data={"name": "New Test"})


@pytest.mark.anyio
async def test_update_view_get(model_view, mock_adapter):
    view, mock_template_response = model_view
    request = Request({"type": "http", "method": "GET", "path": "/1/update"})
    item = MockModel()
    item.id = 1
    item.name = "Test"
    mock_adapter.get.return_value = item
    await view.update_view(request, item_id=1)
    mock_template_response.assert_called_with(
        "update.html",
        {
            "request": request,
            "model_name": "MockModel",
            "item": item,
            "fields": ["id", "name"],
        },
    )


@pytest.mark.anyio
async def test_update_view_post(model_view, mock_adapter):
    view, _ = model_view

    async def form():
        return {"name": "Updated Test"}

    request = Request({"type": "http", "method": "POST", "path": "/1/update"})
    request.form = form
    item = MockModel()
    item.id = 1
    item.name = "Test"
    mock_adapter.get.return_value = item
    response = await view.update_view(request, item_id=1)
    assert response == {"message": "Item updated successfully"}
    mock_adapter.update.assert_called_once_with(pk=1, data={"name": "Updated Test"})


@pytest.mark.anyio
async def test_update_view_not_found(model_view, mock_adapter):
    view, _ = model_view
    request = Request({"type": "http", "method": "GET", "path": "/1/update"})
    mock_adapter.get.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await view.update_view(request, item_id=1)
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_delete_action(model_view, mock_adapter):
    view, _ = model_view
    item = MockModel()
    item.id = 1
    item.name = "Test"
    mock_adapter.get.return_value = item
    response = await view.delete_action(item_id=1)
    assert response == {}
    mock_adapter.delete.assert_called_once_with(pk=1)


@pytest.mark.anyio
async def test_delete_action_not_found(model_view, mock_adapter):
    view, _ = model_view
    mock_adapter.get.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await view.delete_action(item_id=1)
    assert exc_info.value.status_code == 404
