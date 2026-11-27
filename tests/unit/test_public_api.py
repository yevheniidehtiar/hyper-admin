"""Public API snapshot and drift guard (story st-v100-freeze-03).

The public API is defined in ``docs/versioning.md`` ("What is public API"). This module
enumerates that surface from the code and the docs, renders it as one line per entry and
compares it with ``public_api_snapshot.txt`` next to this file:

- every name in ``hyperadmin.__all__``, plus the names ``hyperadmin`` resolves lazily
  (module-level ``_*EXPORTS`` collections read by its ``__getattr__``);
- every ``hyperadmin`` name the docs import or reference (code-block imports, ``:::``
  reference directives and backticked dotted paths in ``docs/`` outside the design records);
- the classes' public members, the settings fields (``HYPERADMIN_*``), the plugin contract
  and the ``hyperadmin`` CLI commands.

A change to the surface fails ``test_public_api_matches_snapshot`` with a diff that names the
added and removed entries and shows the old and the new signature. When the change is
deliberate, regenerate the snapshot explicitly and commit it with the change::

    HYPERADMIN_UPDATE_API_SNAPSHOT=1 uv run pytest tests/unit/test_public_api.py

The regeneration run writes the file and still fails, so a snapshot is never refreshed
silently (for example in CI).
"""

from __future__ import annotations

import dataclasses
import difflib
import enum
import importlib
import inspect
import os
import re
import sys
import types
import typing
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
API_DOCS_DIR = DOCS_DIR / "api"
TESTS_DIR = REPO_ROOT / "tests"
SNAPSHOT_PATH = Path(__file__).with_name("public_api_snapshot.txt")
UPDATE_ENV = "HYPERADMIN_UPDATE_API_SNAPSHOT"

#: Docs that record designs, plans or history, not the supported API (docs/versioning.md).
NON_REFERENCE_DOCS = ("specs", "design", "changelog.md", "roadmap.md")
#: Packages documented as *not* public even though the docs mention them.
NOT_PUBLIC_PREFIXES = ("hyperadmin.loadtest",)
#: The commands of the ``hyperadmin`` CLI that are public (docs/versioning.md, "Command line").
PUBLIC_CLI_COMMANDS = ("createsuperuser", "init-db")

_IMPORT_RE = re.compile(
    r"^\s*from\s+(hyperadmin(?:\.\w+)*)\s+import\s+(\([^)]*\)|[^\n#]+)", re.MULTILINE
)
_DIRECTIVE_RE = re.compile(r"^:::\s+(hyperadmin[\w.]*)\s*$", re.MULTILINE)
_DOTTED_RE = re.compile(r"`(hyperadmin(?:\.\w+)+)")
_ADDRESS_RE = re.compile(r" at 0x[0-9a-fA-F]+")
_LAZY_EXPORTS_RE = re.compile(r"^_[A-Z_]*EXPORTS$")


# --------------------------------------------------------------------------- discovery


def _reference_docs() -> list[Path]:
    """Markdown pages that document the supported API (guides, reference, README)."""
    pages = [
        path
        for path in sorted(DOCS_DIR.rglob("*.md"))
        if not any(part in NON_REFERENCE_DOCS for part in path.relative_to(DOCS_DIR).parts)
    ]
    return [*pages, REPO_ROOT / "README.md"]


def _resolve(path: str) -> Any:
    """Import ``path`` (``package.module.attr``); raise ``LookupError`` when it does not exist."""
    parts = path.split(".")
    for split in range(len(parts), 0, -1):
        try:
            obj: Any = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        for attr in parts[split:]:
            try:
                obj = getattr(obj, attr)
            except AttributeError as exc:  # noqa: PERF203 - fails at most once
                raise LookupError(path) from exc
        return obj
    raise LookupError(path)  # pragma: no cover - every path starts with "hyperadmin"


def _is_public_path(path: str) -> bool:
    return not path.startswith(NOT_PUBLIC_PREFIXES) and not any(
        part.startswith("_") for part in path.split(".")
    )


def documented_imports() -> dict[str, list[str]]:
    """``{dotted path: [pages]}`` for every ``from hyperadmin... import X`` in the docs."""
    found: dict[str, list[str]] = {}
    for page in _reference_docs():
        for match in _IMPORT_RE.finditer(page.read_text(encoding="utf-8")):
            module, names = match.group(1), match.group(2).strip("() \n")
            for chunk in names.split(","):
                name = chunk.split(" as ")[0].strip()
                if name.isidentifier():
                    found.setdefault(f"{module}.{name}", []).append(
                        str(page.relative_to(REPO_ROOT))
                    )
    return found


def documented_directives() -> dict[str, list[str]]:
    """``{dotted path: [pages]}`` for every ``::: hyperadmin...`` reference directive."""
    found: dict[str, list[str]] = {}
    for page in _reference_docs():
        for match in _DIRECTIVE_RE.finditer(page.read_text(encoding="utf-8")):
            found.setdefault(match.group(1), []).append(str(page.relative_to(REPO_ROOT)))
    return found


def documented_references() -> set[str]:
    """Backticked dotted paths (``hyperadmin.filters.DateRangeFilter``) that resolve to objects."""
    paths: set[str] = set()
    for page in _reference_docs():
        for match in _DOTTED_RE.finditer(page.read_text(encoding="utf-8")):
            path = match.group(1)
            try:
                obj = _resolve(path)
            except LookupError:
                continue
            if not isinstance(obj, types.ModuleType):
                paths.add(path)
    return paths


def lazy_top_level_names(module: types.ModuleType) -> set[str]:
    """Names a package resolves in ``__getattr__`` from a ``_*EXPORTS`` dict, set or frozenset."""
    names: set[str] = set()
    for attr, value in vars(module).items():
        if _LAZY_EXPORTS_RE.match(attr) and isinstance(value, dict | set | frozenset):
            names.update(name for name in value if isinstance(name, str))
    return names


def public_paths() -> set[str]:
    """Every dotted path the public API covers (see the module docstring)."""
    hyperadmin = importlib.import_module("hyperadmin")
    paths = {f"hyperadmin.{name}" for name in hyperadmin.__all__}
    paths |= {f"hyperadmin.{name}" for name in lazy_top_level_names(hyperadmin)}
    paths |= set(documented_imports())
    paths |= {path for path in documented_directives() if path != "hyperadmin"}
    paths |= documented_references()
    return {path for path in paths if _is_public_path(path)}


# --------------------------------------------------------------------------- rendering


def _format_annotation(annotation: Any) -> str:  # noqa: PLR0911, PLR0912 - one branch per form
    """Render an annotation the same way on every supported Python version."""
    if annotation is inspect.Parameter.empty:
        return ""
    if isinstance(annotation, str):
        return annotation
    if annotation is None or annotation is type(None):
        return "None"
    if isinstance(annotation, typing.ForwardRef):
        return annotation.__forward_arg__
    if isinstance(annotation, typing.TypeVar):
        return annotation.__name__
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin is typing.Union or (
        sys.version_info >= (3, 10) and isinstance(annotation, types.UnionType)
    ):
        return " | ".join(_format_annotation(arg) for arg in args)
    if origin is typing.Literal:
        return f"Literal[{', '.join(repr(arg) for arg in args)}]"
    if origin is typing.Annotated:
        return _format_annotation(args[0])
    if origin is not None:
        name = getattr(origin, "__qualname__", None) or _format_annotation(origin)
        if not args:
            return name
        if isinstance(args[0], list):  # Callable[[A, B], R]
            params = ", ".join(_format_annotation(arg) for arg in args[0])
            return f"{name}[[{params}], {_format_annotation(args[1])}]"
        return f"{name}[{', '.join(_format_annotation(arg) for arg in args)}]"
    if args == () and isinstance(annotation, list):
        return f"[{', '.join(_format_annotation(arg) for arg in annotation)}]"
    if annotation is Ellipsis:
        return "..."
    name = getattr(annotation, "__qualname__", None) or getattr(annotation, "_name", None)
    return name or repr(annotation).replace("typing.", "")


def _format_default(value: Any) -> str:
    if isinstance(value, frozenset | set):
        inner = ", ".join(sorted(repr(item) for item in value))
        return f"{type(value).__name__}({{{inner}}})"
    if isinstance(value, enum.Enum):
        return f"{type(value).__name__}.{value.name}"
    if inspect.isfunction(value) or inspect.isclass(value):
        return value.__qualname__
    return _ADDRESS_RE.sub("", repr(value))


def _signature(obj: Any) -> inspect.Signature | None:
    kwargs: dict[str, Any] = {}
    if sys.version_info >= (3, 14):  # pragma: no cover - exercised on 3.14+ CI legs
        import annotationlib

        kwargs["annotation_format"] = annotationlib.Format.FORWARDREF
    try:
        return inspect.signature(obj, **kwargs)
    except (TypeError, ValueError):
        return None


def format_signature(obj: Any) -> str:
    """``(a: int, *, b: str = 'x') -> None`` with stable annotations and defaults."""
    sig = _signature(obj)
    if sig is None:
        return "(...)"
    rendered: list[str] = []
    seen_kw_only = False
    for param in sig.parameters.values():
        if param.kind is param.KEYWORD_ONLY and not seen_kw_only:
            rendered.append("*")
            seen_kw_only = True
        prefix = {param.VAR_POSITIONAL: "*", param.VAR_KEYWORD: "**"}.get(param.kind, "")
        if param.kind is param.VAR_POSITIONAL:
            seen_kw_only = True
        text = f"{prefix}{param.name}"
        annotation = _format_annotation(param.annotation)
        if annotation:
            text += f": {annotation}"
        if param.default is not param.empty:
            text += f" = {_format_default(param.default)}"
        rendered.append(text)
    positional_only = [p for p in sig.parameters.values() if p.kind is p.POSITIONAL_ONLY]
    if positional_only:
        rendered.insert(len(positional_only), "/")
    returns = _format_annotation(sig.return_annotation)
    return f"({', '.join(rendered)})" + (f" -> {returns}" if returns else "")


def _own_annotations(cls: type) -> dict[str, Any]:
    if sys.version_info >= (3, 14):  # pragma: no cover - exercised on 3.14+ CI legs
        import annotationlib

        return annotationlib.get_annotations(cls, format=annotationlib.Format.FORWARDREF)
    return dict(inspect.get_annotations(cls))


def _is_hyperadmin(obj: Any) -> bool:
    return str(getattr(obj, "__module__", "") or "").startswith("hyperadmin")


def _pydantic_fields(cls: type) -> dict[str, Any] | None:
    fields = getattr(cls, "model_fields", None)
    return fields if isinstance(fields, dict) and hasattr(cls, "model_config") else None


def _render_pydantic_field(field: Any) -> str:
    text = _format_annotation(field.annotation)
    if field.default_factory is not None:
        return f"{text} = {_format_default(field.default_factory)}()"
    if not field.is_required():
        return f"{text} = {_format_default(field.default)}"
    return text


def _member_kind(raw: Any) -> str | None:
    if isinstance(raw, staticmethod):
        return "staticmethod"
    if isinstance(raw, classmethod):
        return "classmethod"
    if isinstance(raw, property):
        return "property"
    if inspect.iscoroutinefunction(raw):
        return "async def"
    if inspect.isfunction(raw):
        return "def"
    if inspect.isclass(raw):
        return "class"
    return None


def _method_member(raw: Any) -> str | None:
    """Descriptor of a method, property, nested class or enum member defined in a class body."""
    kind = _member_kind(raw)
    if kind in {"staticmethod", "classmethod"}:
        return f"{kind} {format_signature(raw.__func__)}"
    if kind == "property":
        sig = _signature(raw.fget)
        return f"property -> {_format_annotation(sig.return_annotation) if sig else ''}"
    if kind in {"def", "async def"}:
        return f"{kind} {format_signature(raw)}"
    if kind == "class":
        return "class"
    if isinstance(raw, enum.Enum):
        return f"= {raw.value!r}"
    return None


def _annotated_member(klass: type, name: str, annotation: Any) -> str:
    """Descriptor of an annotated class attribute (pydantic field, dataclass field or attr)."""
    pydantic_fields = _pydantic_fields(klass)
    if pydantic_fields is not None and name in pydantic_fields:
        return f"field: {_render_pydantic_field(pydantic_fields[name])}"
    if dataclasses.is_dataclass(klass):
        fields = {f.name: f for f in dataclasses.fields(klass)}
        if name in fields:
            return f"field: {_render_dataclass_field(fields[name])}"
    default = getattr(klass, name, inspect.Parameter.empty)
    text = f"attr: {_format_annotation(annotation)}"
    return f"{text} = {_format_default(default)}" if _is_literal(default) else text


def class_members(cls: type) -> list[tuple[str, str]]:
    """``[(name, descriptor)]`` for the public members HyperAdmin defines on ``cls``."""
    members: dict[str, str] = {}
    for klass in reversed(cls.__mro__):
        if not _is_hyperadmin(klass):
            continue
        annotations = _own_annotations(klass)
        for name, raw in vars(klass).items():
            if name.startswith("_") or name in annotations:
                continue
            descriptor = _method_member(raw)
            if descriptor is not None:
                members[name] = descriptor
        for name, annotation in annotations.items():
            if not name.startswith("_"):
                members[name] = _annotated_member(cls, name, annotation)
    return sorted(members.items())


def _is_literal(value: Any) -> bool:
    """Whether ``value`` has a stable, meaningful ``repr`` (literals and their containers)."""
    if isinstance(value, str | int | float | bool | type(None) | enum.Enum):
        return True
    if isinstance(value, list | tuple | set | frozenset):
        return all(_is_literal(item) for item in value)
    if isinstance(value, dict):
        return all(_is_literal(k) and _is_literal(v) for k, v in value.items())
    return False


def _render_dataclass_field(field: dataclasses.Field[Any]) -> str:
    text = _format_annotation(field.type)
    if field.default is not dataclasses.MISSING:
        return f"{text} = {_format_default(field.default)}"
    if field.default_factory is not dataclasses.MISSING:
        return f"{text} = {_format_default(field.default_factory)}()"
    return text


def describe(obj: Any) -> str:
    """One-line descriptor of a public object (kind and signature or value)."""
    if inspect.isclass(obj):
        bases = ", ".join(base.__qualname__ for base in obj.__bases__ if base is not object)
        head = f"class({bases})" if bases else "class"
        opaque = issubclass(obj, enum.Enum) or getattr(obj, "_is_protocol", False)
        if opaque or _pydantic_fields(obj) is not None:
            return head
        if dataclasses.is_dataclass(obj) or "__init__" in vars(obj) or "__new__" in vars(obj):
            return f"{head} {format_signature(obj)}"
        return head
    if inspect.iscoroutinefunction(obj):
        return f"async def {format_signature(obj)}"
    if inspect.isfunction(obj) or inspect.isbuiltin(obj):
        return f"def {format_signature(obj)}"
    if callable(obj) and hasattr(obj, "__wrapped__"):
        return f"def {format_signature(obj)}"
    if isinstance(obj, str | int | float | bool | tuple | frozenset | set | type(None)):
        return f"= {_format_default(obj)}"
    return f"instance of {type(obj).__qualname__}"


def _cli_lines() -> list[str]:
    import typer

    from hyperadmin.__main__ import app

    group = typer.main.get_command(app)
    lines: list[str] = []
    for name in PUBLIC_CLI_COMMANDS:
        command = group.commands[name]  # type: ignore[attr-defined]
        for param in command.params:
            opts = "/".join([*param.opts, *param.secondary_opts])
            flags = []
            if param.required:
                flags.append("required")
            if getattr(param, "is_flag", False):
                flags.append("flag")
            suffix = f" ({', '.join(flags)})" if flags else ""
            lines.append(f"cli hyperadmin {name} {param.name} :: {opts}{suffix}")
    return lines


def _settings_env_lines(paths: dict[str, Any], canonical: dict[int, str]) -> list[str]:
    lines = []
    for path, obj in paths.items():
        if canonical[id(obj)] != path:
            continue
        if inspect.isclass(obj) and _pydantic_fields(obj) is not None:
            prefix = obj.model_config.get("env_prefix")
            if prefix:
                lines.append(f"env {path} :: env_prefix = {prefix!r}")
    return lines


def build_snapshot() -> list[str]:
    """The public surface, one sorted line per entry."""
    resolved = {path: _resolve(path) for path in sorted(public_paths())}
    canonical: dict[int, str] = {}

    def rank(path: str) -> tuple[bool, int, str]:
        own_name = getattr(resolved[path], "__name__", None)
        return (path.rsplit(".", 1)[1] != own_name, path.count("."), path)

    for path in sorted(resolved, key=rank):
        canonical.setdefault(id(resolved[path]), path)
    lines: list[str] = []
    for path, obj in resolved.items():
        owner = canonical[id(obj)]
        if owner != path and not isinstance(obj, str | int | float | bool | type(None)):
            lines.append(f"{path} :: alias of {owner}")
            continue
        lines.append(f"{path} :: {describe(obj)}")
        if inspect.isclass(obj) and _is_hyperadmin(obj):
            lines.extend(f"{path}.{name} :: {text}" for name, text in class_members(obj))
    lines.extend(_settings_env_lines(resolved, canonical))
    lines.extend(_cli_lines())
    return sorted(lines)


def diff_snapshots(old: list[str], new: list[str]) -> str:
    """Explain a surface change: names added and removed, and old/new signatures side by side."""

    def by_key(lines: list[str]) -> dict[str, str]:
        return dict(line.split(" :: ", 1) for line in lines)

    before, after = by_key(old), by_key(new)
    report = [f"added:   {key} :: {after[key]}" for key in sorted(after.keys() - before.keys())]
    report += [f"removed: {key} :: {before[key]}" for key in sorted(before.keys() - after.keys())]
    report += [
        f"changed: {key}\n    old: {before[key]}\n    new: {after[key]}"
        for key in sorted(before.keys() & after.keys())
        if before[key] != after[key]
    ]
    return "\n".join(report)


# --------------------------------------------------------------------------- tests


def test_public_api_matches_snapshot() -> None:
    """Scenario: the public surface is unchanged unless the snapshot is updated on purpose.

    Given the committed public API snapshot
    When  the surface is rebuilt from the code and the docs
    Then  it matches the snapshot line for line
    """
    current = build_snapshot()
    if os.environ.get(UPDATE_ENV):
        SNAPSHOT_PATH.write_text("\n".join(current) + "\n", encoding="utf-8")
        pytest.fail(
            f"{SNAPSHOT_PATH.name} regenerated; review the diff, then rerun without {UPDATE_ENV}"
        )
    recorded = SNAPSHOT_PATH.read_text(encoding="utf-8").splitlines()
    if current != recorded:
        unified = "\n".join(
            difflib.unified_diff(recorded, current, "snapshot", "code", lineterm="", n=0)
        )
        pytest.fail(
            "The public API changed (docs/versioning.md). If this is deliberate, run\n"
            f"    {UPDATE_ENV}=1 uv run pytest {Path(__file__).relative_to(REPO_ROOT)}\n"
            "and commit the snapshot with the change.\n\n"
            f"{diff_snapshots(recorded, current)}\n\n{unified}"
        )


def test_new_export_is_named_in_the_failure() -> None:
    """Scenario: an export is added without updating the snapshot.

    Given the public API snapshot
    When  a new name is exported from hyperadmin
    Then  the snapshot test fails and names the new export
    """
    # Given
    recorded = build_snapshot()
    # When
    hyperadmin = importlib.import_module("hyperadmin")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(hyperadmin, "__all__", [*hyperadmin.__all__, "NewThing"])
        mp.setattr(
            hyperadmin,
            "NewThing",
            type("NewThing", (), {"__module__": "hyperadmin.x"}),
            raising=False,
        )
        current = build_snapshot()
    # Then
    assert current != recorded
    report = diff_snapshots(recorded, current)
    assert "added:   hyperadmin.NewThing :: class" in report


def test_changed_signature_shows_old_and_new() -> None:
    """Scenario: a public signature changes.

    Given the public API snapshot
    When  a parameter of an exported callable is renamed or removed
    Then  the snapshot test fails and shows the old and the new signature
    """
    # Given
    recorded = build_snapshot()
    hyperadmin = importlib.import_module("hyperadmin")

    def gettext_lazy(renamed: str) -> str:
        """Stand-in whose parameter was renamed."""
        return renamed

    # When
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(hyperadmin, "gettext_lazy", gettext_lazy)
        current = build_snapshot()
    # Then
    report = diff_snapshots(recorded, current)
    old = next(line for line in recorded if line.startswith("hyperadmin.gettext_lazy :: "))
    assert "(message: str)" in old
    assert "changed: hyperadmin.gettext_lazy" in report
    assert f"old: {old.split(' :: ', 1)[1]}" in report
    assert "new: def (renamed: str) -> str" in report


def test_every_export_has_a_reference_entry() -> None:
    """Scenario: an export has no reference entry.

    Given the list of exported names
    When  the docs reference is checked
    Then  every name is found under docs/api
    """
    # Given
    paths = public_paths()
    # When
    reference = "\n".join(page.read_text(encoding="utf-8") for page in API_DOCS_DIR.rglob("*.md"))
    rendered = [_resolve(path) for path in _DIRECTIVE_RE.findall(reference) if path != "hyperadmin"]
    missing = sorted(
        path
        for path in paths
        if not re.search(
            rf"`(?:{re.escape(path)}|{re.escape(path.rsplit('.', 1)[1])})\b", reference
        )
        and not any(_resolve(path) is obj for obj in rendered)
    )
    # Then
    assert not missing, f"no docs/api entry for: {missing}"


def test_documented_imports_resolve() -> None:
    """Scenario: the docs only import names that exist.

    Given every ``from hyperadmin... import X`` and ``::: hyperadmin...`` in the docs
    When  each path is imported
    Then  it resolves
    """
    broken = {}
    for path, pages in {**documented_imports(), **documented_directives()}.items():
        try:
            _resolve(path)
        except LookupError:  # noqa: PERF203 - a readable report beats speed here
            broken[path] = pages
    assert not broken, f"docs reference names that do not exist: {broken}"


def _public_callables() -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for path in sorted(public_paths()):
        obj = _resolve(path)
        if inspect.isfunction(obj):
            items.append((path, obj))
        elif inspect.isclass(obj) and _is_hyperadmin(obj):
            for klass in obj.__mro__:
                if not _is_hyperadmin(klass):
                    continue
                for name, raw in vars(klass).items():
                    func = getattr(raw, "__func__", raw)
                    public = not name.startswith("_") or name == "__init__"
                    own = inspect.isfunction(func) and _is_hyperadmin(func)
                    if public and own and func.__qualname__.startswith(f"{klass.__qualname__}."):
                        items.append((f"{path}.{name}", func))
    return items


def test_every_export_has_a_docstring() -> None:
    """Scenario: every public object explains itself.

    Given the public surface
    When  each class, function and public method is inspected
    Then  it has its own docstring
    """
    missing = []
    for path in sorted(public_paths()):
        obj = _resolve(path)
        if not (inspect.isclass(obj) or inspect.isfunction(obj)):
            continue
        doc = obj.__doc__ or ""
        generated = dataclasses.is_dataclass(obj) and doc.startswith(f"{obj.__name__}(")
        if not doc.strip() or generated:
            missing.append(path)
    missing += [
        path
        for path, func in _public_callables()
        if not path.endswith(".__init__") and not (inspect.getdoc(func) or "").strip()
    ]
    assert not missing, f"public objects without a docstring: {sorted(set(missing))}"


def test_every_public_callable_is_fully_annotated() -> None:
    """Scenario: every public signature is typed.

    Given the public functions and methods
    When  their signatures are inspected
    Then  every parameter (except ``self``/``cls``) and the return value are annotated
    """
    gaps = []
    for path, func in _public_callables():
        sig = _signature(func)
        assert sig is not None
        params = list(sig.parameters.values())
        if params and params[0].name in {"self", "cls"}:
            params = params[1:]
        unannotated = [p.name for p in params if p.annotation is p.empty]
        if sig.return_annotation is sig.empty:
            unannotated.append("return")
        if unannotated:
            gaps.append(f"{path}: {unannotated}")
    assert not gaps, "public callables with missing annotations:\n" + "\n".join(gaps)


def test_every_export_is_used_by_a_test() -> None:
    """Scenario: every public name is exercised.

    Given the public surface
    When  the test suite is searched
    Then  each name appears in at least one test other than this snapshot
    """
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in TESTS_DIR.rglob("*.py")
        if path.resolve() != Path(__file__).resolve()
    )
    untested = sorted(
        path
        for path in public_paths()
        if not re.search(rf"\b{re.escape(path.rsplit('.', 1)[1])}\b", sources)
    )
    assert not untested, f"public names no test refers to: {untested}"


def test_lazy_top_level_names_are_collected() -> None:
    """Scenario: names a package resolves lazily are part of the surface.

    Given a package with a ``_LAZY_EXPORTS`` mapping read by its ``__getattr__``
    When  its lazy names are collected
    Then  the mapping's keys are returned and unrelated private globals are not
    """
    module = types.ModuleType("fake")
    module._LAZY_EXPORTS = {"Lazy": "fake.impl"}  # type: ignore[attr-defined]
    module._OAUTH_EXPORTS = frozenset({"Other"})  # type: ignore[attr-defined]
    module._unrelated = {"Hidden"}  # type: ignore[attr-defined]
    assert lazy_top_level_names(module) == {"Lazy", "Other"}


def test_annotations_render_the_same_on_every_python() -> None:
    """Scenario: the snapshot does not depend on the Python version.

    Given typing forms whose ``repr`` differs between Python versions
    When  they are rendered for the snapshot
    Then  each renders in one normalised spelling
    """
    from collections.abc import Callable

    assert _format_annotation(typing.Optional[int]) == "int | None"  # noqa: UP045
    assert _format_annotation(int | None) == "int | None"
    assert _format_annotation(typing.Union[int, str]) == "int | str"  # noqa: UP007
    assert _format_annotation(typing.Literal["a", "b"]) == "Literal['a', 'b']"
    assert _format_annotation(typing.Annotated[int, "meta"]) == "int"
    assert _format_annotation(Callable[[int, str], None]) == "Callable[[int, str], None]"
    assert _format_annotation(dict[str, list[int]]) == "dict[str, list[int]]"
    assert _format_annotation(typing.ForwardRef("Admin")) == "Admin"
    assert _format_annotation("Admin") == "Admin"
    assert _format_default(frozenset({"b", "a"})) == "frozenset({'a', 'b'})"
    assert _format_default(object()).startswith("<object object>")


def test_snapshot_sections_are_present() -> None:
    """Scenario: the snapshot covers settings, plugins and the CLI as well as imports.

    Given the rebuilt public surface
    When  it is searched for each surface named in docs/versioning.md
    Then  settings fields, the plugin contract, lifecycle hooks and the CLI commands are there
    """
    lines = build_snapshot()
    text = "\n".join(lines)
    assert "hyperadmin.HyperAdminSettings.secret_key :: field:" in text
    assert "env hyperadmin.HyperAdminSettings :: env_prefix = 'HYPERADMIN_'" in text
    assert "hyperadmin.Plugin.on_register :: def" in text
    assert "hyperadmin.PluginRegistry.add_page :: def" in text
    assert "hyperadmin.core.plugins.LIFECYCLE_HOOKS :: = frozenset(" in text
    assert any(line.startswith("cli hyperadmin init-db ") for line in lines)
    assert any(line.startswith("cli hyperadmin createsuperuser ") for line in lines)
