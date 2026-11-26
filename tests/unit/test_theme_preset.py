"""Theme presets: ``<html data-ha-preset>`` follows ``HyperAdminSettings.theme_preset``.

Scenario: the terminal preset is rendered by default
  Given no theme_preset template global
  When  _base.html renders
  Then  <html data-ha-preset="terminal">
  And   the favicon is the terminal "h:" mark

Scenario: the classic preset is rendered when chosen
  Given the theme_preset template global is "classic"
  When  _base.html renders
  Then  <html data-ha-preset="classic">
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.testclient import TestClient

from hyperadmin.i18n.loader import install_jinja_i18n
from hyperadmin.i18n.middleware import RTL_LOCALES

_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "hyperadmin"
)
_CSS_DIR = os.path.join(_SRC, "static", "css")


def _render_base(theme_preset: str | None) -> str:
    templates = Jinja2Templates(directory=os.path.join(_SRC, "templates"))
    install_jinja_i18n(templates.env)
    templates.env.globals.update(
        rtl_locales=RTL_LOCALES,
        theme="auto",
        site_title="HyperAdmin",
        site_header="HyperAdmin",
        admin_prefix="/admin",
        auth_enabled=False,
        supported_locales=["en"],
    )
    if theme_preset is not None:
        templates.env.globals["theme_preset"] = theme_preset

    app = FastAPI()
    app.mount("/static", StaticFiles(directory=os.path.join(_SRC, "static")), name="static")

    @app.get("/")
    async def root(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "_base.html", {})  # type: ignore[return-value]

    response = TestClient(app).get("/")
    assert response.status_code == 200
    return response.text


def test_terminal_preset_is_rendered_by_default() -> None:
    # Given no theme_preset template global / When _base.html renders
    body = _render_base(None)
    # Then <html data-ha-preset="terminal">
    assert 'data-ha-preset="terminal"' in body
    # And the favicon is the terminal "h:" mark
    assert "/img/terminal/hyperadmin-favicon.svg" in body


def test_classic_preset_is_rendered_when_chosen() -> None:
    # Given theme_preset "classic" / When _base.html renders
    body = _render_base("classic")
    # Then <html data-ha-preset="classic">
    assert 'data-ha-preset="classic"' in body
    # And the favicon is the classic mark
    assert "/img/terminal/" not in body
    assert "/img/hyperadmin-favicon.svg" in body


def test_terminal_stylesheets_are_imported() -> None:
    """
    Scenario: the bundle loads the terminal preset after the classic tokens
      Given hyperadmin.css
      When  its imports are read
      Then  _theme-terminal.css follows _dark-mode.css in the tokens layer
      And   _theme-terminal-type.css sits in the components layer
    """
    with open(os.path.join(_CSS_DIR, "hyperadmin.css"), encoding="utf-8") as fh:
        css = fh.read()
    assert css.index('"_dark-mode.css"') < css.index('@import "_theme-terminal.css" layer(tokens);')
    assert '@import "_theme-terminal-type.css" layer(components);' in css
    for name in ("_theme-terminal.css", "_theme-terminal-type.css"):
        assert os.path.isfile(os.path.join(_CSS_DIR, name))
