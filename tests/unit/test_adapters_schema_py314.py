"""Python 3.14 lazy annotations must not break schema building (#770)."""

import inspect
import sys
import types
from typing import Any

import pytest

from hyperadmin.adapters import schema as schema_mod


def test_base_hints_survive_lazy_annotations_naming_missing_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: a model naming a TYPE_CHECKING-only class still builds a schema
      Given get_type_hints and inspect.get_annotations both raise NameError (Python 3.14)
      When  the base hints are collected
      Then  the forward-ref-tolerant annotations are used and string refs are dropped
    """

    class Plain:
        pass

    def _raise(*_a: Any, **_k: Any) -> Any:
        raise NameError("Group")

    fake = types.SimpleNamespace(
        Format=types.SimpleNamespace(FORWARDREF="fwd"),
        get_annotations=lambda _base, **_kw: {"id": int, "rel": "Group"},
    )
    monkeypatch.setitem(sys.modules, "annotationlib", fake)
    monkeypatch.setattr(schema_mod, "get_type_hints", _raise)
    monkeypatch.setattr(inspect, "get_annotations", _raise)

    assert schema_mod._base_hints(Plain) == {"id": int}
