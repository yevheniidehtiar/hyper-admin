from unittest.mock import MagicMock, Mock

from fastapi.templating import Jinja2Templates

from hyperadmin.routing import HyperAdminRouter


def test_hyper_admin_router_instantiation():
    mock_engine = Mock()
    mock_templates = MagicMock(spec=Jinja2Templates)
    router = HyperAdminRouter(engine=mock_engine, templates=mock_templates)
    assert router.engine == mock_engine
    assert router.templates == mock_templates
    assert router.router is not None
