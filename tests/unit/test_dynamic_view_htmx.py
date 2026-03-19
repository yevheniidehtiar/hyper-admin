from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import BaseModel
from starlette.datastructures import URL
from starlette.requests import Request
from starlette.responses import Response

from hyperadmin.adapters.registry import adapter_registry
from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.core.registry import site
from hyperadmin.views import dynamic as dynamic_module


class DummyAdapter(BaseAdapter):
    def __init__(self, model):
        self.model = model

    async def get(self, pk):
        if pk == 999:
            return None
        return SimpleNamespace(id=pk, name="Test", model_dump=lambda: {"id": pk, "name": "Test"})

    async def list(self, **kwargs):
        return [SimpleNamespace(id=1, name="Test")], 1

    async def create(self, data):
        if data.get("no_id"):
            return SimpleNamespace(**data)
        return SimpleNamespace(id=1, **data)

    async def update(self, pk, data):
        return SimpleNamespace(id=pk, **data)

    async def delete(self, pk):
        pass

    async def get_related(self, pk, field):
        return []

    async def get_schema(self):
        return {}


class User(BaseModel):
    name: str
    is_active: bool = True


class FakeHtmxResponder:
    """Fake replacement for HtmxTemplateResponse used to observe calls."""

    def __init__(self, templates):  # pragma: no cover - simple passthrough
        self.templates = templates

    def render(
        self,
        *,
        template_name: str,
        context: dict,
        request: Request,
        block: str | None,
        status_code: int | None = None,
    ):
        # Assert that DynamicModelView requests the inner form block
        assert block == "form_body"
        # Return a recognizable Response
        return Response(content=f"BLOCK:{template_name}")


@pytest.fixture
def request_factory():
    def _make(
        headers: dict[str, str] | None = None, method: str = "GET", form_data: dict | None = None
    ) -> Request:
        async def form():
            return form_data or {"name": "Test"}

        scope = {
            "type": "http",
            "method": method,
            "path": "/",
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
            "app": SimpleNamespace(
                url_path_for=lambda name, **kw: SimpleNamespace(
                    make_absolute_url=lambda base_url=None, **kwargs: URL(f"/{name}")
                )
            ),
        }
        request = Request(scope)
        if method == "POST":
            request.form = form
        return request

    return _make


@pytest.fixture(autouse=True)
def patch_htmx(monkeypatch):
    # Patch HtmxTemplateResponse class used in dynamic module
    monkeypatch.setattr(dynamic_module, "HtmxTemplateResponse", FakeHtmxResponder)


@pytest.fixture
def view(tmp_path):
    # Build a minimal Jinja2Templates that points to real templates dir so that
    # _get_template_name resolves create/update.html present in the repo.
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="src/hyperadmin/templates")

    view = dynamic_module.DynamicModelView(
        adapter=DummyAdapter(User),
        options=SimpleNamespace(),
        templates=templates,
        app_label=None,
    )
    return view


@pytest.fixture
def register_dummy_adapter():
    adapter_registry.register(User, DummyAdapter)
    yield
    if User in adapter_registry._registry:
        del adapter_registry._registry[User]


def test_init_subclass(register_dummy_adapter):
    class MyModel(User):
        pass

    class MyModelAdmin(dynamic_module.ModelView, model=MyModel):
        pass

    assert MyModel in site._registry
    admin_class = site._registry[MyModel]
    assert admin_class == MyModelAdmin
    site.unregister(MyModel)


def test_init_subclass_no_model():
    class MyModelAdmin(dynamic_module.ModelView):
        pass

    assert not hasattr(MyModelAdmin, "model")


def test_model_view_subclass_registration():
    class OtherModel(BaseModel):
        pass

    with patch("hyperadmin.views.dynamic.site.register") as mock_register:

        class OtherModelAdmin(dynamic_module.ModelView, model=OtherModel):
            pass

        mock_register.assert_called_once()
        call_args, call_kwargs = mock_register.call_args
        assert call_args[0] == OtherModel
        assert call_kwargs["admin_class"] == OtherModelAdmin


@pytest.mark.anyio
async def test_create_form_view_uses_block_for_htmx(request_factory, view):
    req = request_factory({"hx-request": "true"})
    resp = await view.create_form_view(req)
    assert isinstance(resp, Response)
    assert resp.body.decode(resp.charset).startswith("BLOCK:")
    assert resp.body.decode(resp.charset).endswith("create.html")


@pytest.mark.anyio
async def test_create_view_redirect(request_factory, view):
    req = request_factory(method="POST")
    resp = await view.create_view(req)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/user-detail"


@pytest.mark.anyio
async def test_create_view_htmx_redirect(request_factory, view):
    req = request_factory(method="POST", headers={"hx-request": "true"})
    resp = await view.create_view(req)
    assert resp.status_code == 200
    assert resp.headers["hx-redirect"] == "/user-detail"


@pytest.mark.anyio
async def test_create_view_exception(request_factory, view, monkeypatch):
    async def fake_create(data):
        raise Exception("DB error")

    monkeypatch.setattr(view.adapter, "create", fake_create)
    req = request_factory(method="POST")
    with pytest.raises(Exception, match="DB error"):
        await view.create_view(req)


@pytest.mark.anyio
async def test_update_form_view_uses_block_for_htmx(request_factory, view):
    req = request_factory({"hx-request": "true"})
    resp = await view.update_form_view(req, item_id=1)
    assert isinstance(resp, Response)
    assert resp.body.decode(resp.charset).startswith("BLOCK:")
    assert resp.body.decode(resp.charset).endswith("update.html")


@pytest.mark.anyio
async def test_update_form_view_not_found(request_factory, view):
    req = request_factory({"hx-request": "true"})
    with pytest.raises(Exception, match="Item not found"):
        await view.update_form_view(req, item_id=999)


@pytest.mark.anyio
async def test_update_view(request_factory, view):
    req = request_factory(method="POST")
    resp = await view.update_view(req, item_id=1)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/user-list"


@pytest.mark.anyio
async def test_delete_action(request_factory, view):
    req = request_factory(method="POST")
    resp = await view.delete_action(req, item_id=1)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/user-list"


@pytest.mark.anyio
async def test_delete_action_not_found(request_factory, view):
    req = request_factory(method="POST")
    with pytest.raises(Exception, match="Item not found"):
        await view.delete_action(req, item_id=999)


@pytest.mark.anyio
async def test_admin_dashboard(request_factory, view):
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="src/hyperadmin/templates")
    req = request_factory()
    resp = await dynamic_module.admin_dashboard(req, templates)
    assert resp.template.name == "dashboard.html"
