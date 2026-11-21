"""The ERP example's dashboard offers only the quick actions the user may take.

The create pages answer 403 without ``add_<model>``, so the "Quick Actions"
card must not link a read-only user there. The template is rendered on its own,
with a stub ``_base.html``, so the test needs no running admin.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[2] / "examples" / "erp" / "templates"
LINKS = ("/admin/invoice/create", "/admin/bill/create", "/admin/contact/create")


def _render(state: SimpleNamespace) -> str:
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"_base.html": "{% block content %}{% endblock %}"}),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
    )
    env.globals["_"] = lambda text: text
    template = env.get_template("dashboard.html")
    return template.render(request=SimpleNamespace(state=state), admin_prefix="/admin")


def test_a_read_only_user_gets_no_quick_create_links() -> None:
    """
    Scenario: a read-only user gets no quick create links
      Given demo_ro holds only view_* permissions
      When  the ERP dashboard renders
      Then  it links to none of the create pages
    """
    html = _render(SimpleNamespace(user_permissions=frozenset({"view_invoice", "view_bill"})))

    assert not [link for link in LINKS if link in html]


def test_quick_actions_follow_each_add_permission() -> None:
    """
    Scenario: each quick action follows its own add permission
      Given a user holding add_invoice only
      When  the ERP dashboard renders
      Then  only "Create New Invoice" is offered
    """
    html = _render(SimpleNamespace(user_permissions=frozenset({"add_invoice"})))

    assert "/admin/invoice/create" in html
    assert "/admin/bill/create" not in html
    assert "/admin/contact/create" not in html


@pytest.mark.parametrize(
    "state",
    [SimpleNamespace(user_permissions=None), SimpleNamespace()],
    ids=["superuser", "auth-disabled"],
)
def test_an_unrestricted_user_gets_every_quick_action(state: SimpleNamespace) -> None:
    """
    Scenario: an unrestricted user gets every quick action
      Given a superuser (no permission set) or an admin without auth
      When  the ERP dashboard renders
      Then  all three create links are offered
    """
    html = _render(state)

    assert all(link in html for link in LINKS)
