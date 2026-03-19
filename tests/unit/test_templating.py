import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.templating import Jinja2Templates

from hyperadmin.core.options import AdminOptions
from hyperadmin.views.dynamic import DynamicModelView


class MockModel:
    __name__ = "MyModel"


@pytest.fixture
def mock_templates():
    templates = MagicMock(spec=Jinja2Templates)
    templates.env = MagicMock()
    templates.env.loader = MagicMock()
    templates.env.loader.searchpath = []
    return templates


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.model = MockModel
    return adapter


@pytest.fixture
def mock_options():
    return MagicMock(spec=AdminOptions)


def test_get_template_name_hierarchy(mock_adapter, mock_templates, mock_options):
    # Arrange
    app_label = "my_app"
    view_name = "list"

    view = DynamicModelView(
        adapter=mock_adapter,
        templates=mock_templates,
        app_label=app_label,
        options=mock_options,
    )

    search_paths = ["/custom_templates"]
    view.templates.env.loader.searchpath = search_paths

    test_cases = [
        (f"{app_label}/{view.model.__name__.lower()}/{view_name}.html", True),
        (f"{app_label}/{view.model.__name__.lower()}/default.html", True),
        (f"{app_label}/{view_name}.html", True),
        (f"{app_label}/default.html", True),
        (f"{view_name}.html", True),
        ("default.html", True),
    ]

    for template_path, _should_exist in test_cases:
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda path, t=template_path: (
                path == os.path.join(search_paths[0], t)
            )

            # Act
            resolved_template = view._get_template_name(view_name)

            # Assert
            assert resolved_template == template_path

    # Test fallback
    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = False
        resolved_template = view._get_template_name(view_name)
        assert resolved_template == f"{view_name}.html"
