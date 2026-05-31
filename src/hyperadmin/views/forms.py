from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Union, get_args, get_origin

from markupsafe import Markup
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

from hyperadmin.core.choices import ChoiceItem
from hyperadmin.i18n import gettext_lazy

try:
    from hyperadmin.core.fields import classify_field as _classify_field

    _HAS_CLASSIFY = True
except ImportError:
    _classify_field = None  # type: ignore[assignment]
    _HAS_CLASSIFY = False

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.templating import Jinja2Templates

    from hyperadmin.core.fieldsets import FieldsetSpec
    from hyperadmin.core.inlines import InlineModelSpec
    from hyperadmin.core.layouts import FormLayout

# Type alias: errors can be lazy-translated proxies or plain strings.
# ``babel.support.LazyProxy`` satisfies the string protocol via ``__str__``.
ErrorList = list[Any]


@dataclass(slots=True)
class HtmxWidget:
    """A minimal widget abstraction capable of rendering via a Jinja template.

    template_path: path to template included under the project templates directory.
    static_list: optional JS/CSS assets to include once per page.
    htmx_attrs: optional HTMX attributes to include on the input element.
    input_type: HTML input type string returned to templates (e.g. ``"text"``, ``"number"``).
    """

    template_path: str
    static_list: tuple[str, ...] = ()
    htmx_attrs: Mapping[str, str] | None = None
    input_type: ClassVar[str] = "text"

    def render(self, templates: Jinja2Templates, form_field: FormField, request) -> Markup:
        context = {
            "request": request,
            "field": form_field,
            "widget": self,
        }
        return Markup(templates.get_template(self.template_path).render(context))  # noqa: S704


class TextInput(HtmxWidget):
    input_type: ClassVar[str] = "text"

    def __init__(self):
        super().__init__(template_path="widgets/text_input.html")


class NumberInput(HtmxWidget):
    input_type: ClassVar[str] = "number"

    def __init__(self):
        super().__init__(template_path="widgets/number_input.html")


class FloatInput(HtmxWidget):
    input_type: ClassVar[str] = "number"

    def __init__(self):
        super().__init__(template_path="widgets/float_input.html")


class Textarea(HtmxWidget):
    def __init__(self):
        super().__init__(template_path="widgets/textarea.html")


class CheckboxInput(HtmxWidget):
    input_type: ClassVar[str] = "checkbox"

    def __init__(self):
        super().__init__(template_path="widgets/checkbox_input.html")


class SelectInput(HtmxWidget):
    def __init__(self):
        super().__init__(template_path="widgets/select_input.html")


class SelectWidget(HtmxWidget):
    """Widget for a single-select with a pre-built choices list."""

    choices: list[ChoiceItem]

    def __init__(self, choices: list[ChoiceItem] | None = None) -> None:
        # HtmxWidget is slots=True; bypass super().__init__ to avoid the
        # zero-arg super() cell-variable issue introduced by @dataclass(slots=True).
        object.__setattr__(self, "template_path", "widgets/select_input.html")
        object.__setattr__(self, "static_list", ())
        object.__setattr__(self, "htmx_attrs", None)
        self.choices = choices or []


class MultiSelectWidget(HtmxWidget):
    """Widget for a multi-select with a pre-built choices list."""

    choices: list[ChoiceItem]

    def __init__(self, choices: list[ChoiceItem] | None = None) -> None:
        object.__setattr__(self, "template_path", "widgets/multiselect_input.html")
        object.__setattr__(self, "static_list", ())
        object.__setattr__(self, "htmx_attrs", None)
        self.choices = choices or []


class DateTimeInput(HtmxWidget):
    input_type: ClassVar[str] = "datetime-local"

    def __init__(self):
        super().__init__(template_path="widgets/datetime_input.html")


class FileInputWidget(HtmxWidget):
    """Widget for file upload fields (``FileType`` / ``ImageType`` columns)."""

    input_type: ClassVar[str] = "file"
    is_image: bool
    current_file: str | None

    def __init__(
        self,
        is_image: bool = False,
        current_file: str | None = None,
    ) -> None:
        object.__setattr__(self, "template_path", "widgets/file_input.html")
        object.__setattr__(self, "static_list", ())
        object.__setattr__(self, "htmx_attrs", None)
        self.is_image = is_image
        self.current_file = current_file


class RelationSelectWidget(HtmxWidget):
    """Widget for a single FK relation field — supports preload and lazy (HTMX) strategies."""

    choices: list[ChoiceItem]
    choices_url: str
    preload: bool
    dependent_on: str | None

    def __init__(
        self,
        choices_url: str,
        choices: list[ChoiceItem] | None = None,
        preload: bool = True,
        dependent_on: str | None = None,
    ) -> None:
        object.__setattr__(self, "template_path", "widgets/relation_select_input.html")
        object.__setattr__(self, "static_list", ())
        object.__setattr__(self, "htmx_attrs", None)
        self.choices = choices or []
        self.choices_url = choices_url
        self.preload = preload
        self.dependent_on = dependent_on


class RelationMultiSelectWidget(HtmxWidget):
    """Widget for a M2M relation field — supports preload and lazy (HTMX) strategies."""

    choices: list[ChoiceItem]
    choices_url: str
    preload: bool
    dependent_on: str | None

    def __init__(
        self,
        choices_url: str,
        choices: list[ChoiceItem] | None = None,
        preload: bool = True,
        dependent_on: str | None = None,
    ) -> None:
        object.__setattr__(self, "template_path", "widgets/relation_multiselect_input.html")
        object.__setattr__(self, "static_list", ())
        object.__setattr__(self, "htmx_attrs", None)
        self.choices = choices or []
        self.choices_url = choices_url
        self.preload = preload
        self.dependent_on = dependent_on


def hybrid_to_python(raw: str | list[str], storage: Literal["json", "csv"]) -> list[str]:
    """Deserialise a stored hybrid list field back to a Python list of strings."""
    if isinstance(raw, list):
        return [str(v) for v in raw]
    if not raw:
        return []
    if storage == "json":
        parsed = json.loads(raw)
        return [str(v) for v in parsed]
    # csv
    return [v.strip() for v in raw.split(",") if v.strip()]


def hybrid_to_storage(value: list[str], storage: Literal["json", "csv"]) -> str:
    """Serialise a Python list of strings to the chosen storage format."""
    if storage == "json":
        return json.dumps(value)
    return ",".join(value)


@dataclass(slots=True)
class FormField:
    name: str
    model_field: FieldInfo
    widget: HtmxWidget
    value: Any | None = None
    errors: ErrorList | None = None

    @property
    def label(self) -> str:
        t = getattr(self.model_field, "title", None)
        return t or self.name.replace("_", " ").capitalize()

    @property
    def required(self) -> bool:
        return bool(self.model_field.is_required)

    @property
    def help_text(self) -> str | None:
        return getattr(self.model_field, "description", None)

    @property
    def input_type(self) -> str:
        ann = getattr(self.model_field, "annotation", None)
        try:
            return ann.__name__ if ann else "text"
        except AttributeError:
            return "text"


@dataclass(slots=True)
class FieldsetGroup:
    """A resolved group of ``FormField`` instances for template rendering.

    Attributes:
        name: Display heading for the fieldset.
        fields: The ``FormField`` instances belonging to this group.
        collapsed: Whether the fieldset starts collapsed.
        description: Optional help text shown under the heading.
        slug: URL-safe identifier derived from *name*, used in ``data-testid``.
    """

    name: str
    fields: list[FormField]
    collapsed: bool = False
    description: str | None = None
    slug: str = ""

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = self.name.lower().replace(" ", "-")


class PydanticForm:
    def __init__(
        self,
        model: type[BaseModel],
        *,
        widgets: dict[str, HtmxWidget] | None = None,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        initial: dict[str, Any] | None = None,
        choices_base_url: str = "",
        fieldsets: list[FieldsetSpec] | None = None,
        form_layout: FormLayout | None = None,
        form_fields: list[str] | None = None,
    ) -> None:
        self.model = model
        self.widgets = widgets or {}
        self.include = set(include or [])
        self.exclude = set(exclude or [])
        self.initial = initial or {}
        self.choices_base_url = choices_base_url
        self.errors: dict[str, ErrorList] = {}
        self._fields: list[FormField] = []
        self._fieldset_specs: list[FieldsetSpec] = fieldsets or []
        self._form_layout: FormLayout | None = form_layout
        self._form_fields: list[str] = form_fields or []

    @staticmethod
    def _enum_choices(enum_cls: type[Enum]) -> list[ChoiceItem]:
        return [
            ChoiceItem(
                value=member.value,
                label=member.name,
                selected=False,
            )
            for member in enum_cls
        ]

    def _pick_widget(self, name: str, field: FieldInfo) -> HtmxWidget:  # noqa: PLR0911, PLR0912
        if name in self.widgets:
            return self.widgets[name]

        # --- classify_field auto-detection (requires SQLAlchemy) ---
        if _HAS_CLASSIFY and _classify_field is not None:
            from hyperadmin.core.choices import SelectFieldMeta  # noqa: PLC0415
            from hyperadmin.core.uploads import FileFieldMeta  # noqa: PLC0415

            raw_meta = _classify_field(field, self.model)
            if isinstance(raw_meta, FileFieldMeta):
                return FileInputWidget(is_image=raw_meta.is_image)
            if isinstance(raw_meta, SelectFieldMeta):
                meta = raw_meta
                choices_url = f"{self.choices_base_url}/{name}" if self.choices_base_url else ""
                if meta.choices_source == "enum":
                    # Extract enum type for choices
                    ann = getattr(field, "annotation", None)
                    origin = get_origin(ann)
                    args = get_args(ann)
                    if origin is not None and args and origin is Union and type(None) in args:
                        ann = next(a for a in args if a is not type(None))
                    # Unwrap list[Enum]
                    if get_origin(ann) is list and get_args(ann):
                        ann = get_args(ann)[0]
                    enum_choices = (
                        self._enum_choices(ann)
                        if isinstance(ann, type) and issubclass(ann, Enum)
                        else []
                    )
                    if meta.multiple:
                        return MultiSelectWidget(choices=enum_choices)
                    return SelectWidget(choices=enum_choices)
                if meta.choices_source == "static" and meta.multiple:
                    return MultiSelectWidget()
                if meta.choices_source == "relation":
                    if meta.multiple:
                        return RelationMultiSelectWidget(
                            choices_url=choices_url,
                            preload=meta.preload,
                            dependent_on=meta.dependent_on,
                        )
                    return RelationSelectWidget(
                        choices_url=choices_url,
                        preload=meta.preload,
                        dependent_on=meta.dependent_on,
                    )

        # --- Legacy heuristics ---
        lower = name.lower()
        if lower in {"description", "text", "body", "content"}:
            return Textarea()

        ann = getattr(field, "annotation", None)
        origin = get_origin(ann)
        args = get_args(ann)

        if origin is not None and args and origin is Union and type(None) in args:
            ann = next(arg for arg in args if arg is not type(None))

        if ann is bool:
            return CheckboxInput()
        if ann is int:
            return NumberInput()
        if ann is float:
            return FloatInput()
        if ann is datetime:
            return DateTimeInput()
        if isinstance(ann, type) and issubclass(ann, Enum):
            return SelectInput()
        return TextInput()

    @staticmethod
    def _is_auto_now_field(field: FieldInfo) -> bool:
        if isinstance(field, FieldInfo):
            sa_column_kwargs = getattr(field, "sa_column_kwargs", None)
            if (
                sa_column_kwargs
                and isinstance(sa_column_kwargs, dict)
                and ("server_default" in sa_column_kwargs or "onupdate" in sa_column_kwargs)
            ):
                return True
            if field.default_factory == datetime.now:
                return True
        return False

    def _build_all_fields(self) -> dict[str, FormField]:
        """Build all eligible form fields as a name->FormField mapping."""
        field_map: dict[str, FormField] = {}
        for name, field in self.model.model_fields.items():
            if self.include and name not in self.include:
                continue
            if name in self.exclude:
                continue
            if name == "id":
                continue
            if self._is_auto_now_field(field):
                continue
            widget = self._pick_widget(name, field)
            default_val = getattr(field, "default", None)
            if str(default_val) == "PydanticUndefined":
                default_val = None
            value = self.initial.get(name, default_val if default_val is not None else None)
            field_map[name] = FormField(name=name, model_field=field, widget=widget, value=value)
        return field_map

    @property
    def fields(self) -> list[FormField]:
        if self._fields:
            return self._fields

        field_map = self._build_all_fields()

        # If form_fields is specified, use that ordering (and only those fields)
        if self._form_fields:
            for name in self._form_fields:
                if name in field_map:
                    self._fields.append(field_map[name])
        else:
            # Default: model-definition order
            self._fields = list(field_map.values())

        return self._fields

    @property
    def fieldset_groups(self) -> list[FieldsetGroup]:
        """Return form fields grouped according to the configured fieldsets.

        If no fieldsets are configured, returns a single group containing all fields.
        Fields referenced in a fieldset spec but not present in the form are silently
        skipped. Fields not covered by any fieldset are collected into a trailing
        "Other fields" group.
        """
        all_fields = self.fields
        if not self._fieldset_specs:
            return [FieldsetGroup(name="", fields=all_fields, slug="")]

        field_map = {f.name: f for f in all_fields}
        claimed: set[str] = set()
        groups: list[FieldsetGroup] = []

        for spec in self._fieldset_specs:
            group_fields: list[FormField] = []
            for fname in spec.fields:
                if fname in field_map:
                    group_fields.append(field_map[fname])
                    claimed.add(fname)
            if group_fields:
                groups.append(
                    FieldsetGroup(
                        name=spec.name,
                        fields=group_fields,
                        collapsed=spec.collapsed,
                        description=spec.description,
                    )
                )

        # Collect unclaimed fields into a default group
        remaining = [f for f in all_fields if f.name not in claimed]
        if remaining:
            groups.append(FieldsetGroup(name="Other fields", fields=remaining))

        return groups

    def bind(self, data: dict[str, Any]) -> None:
        for f in self.fields:
            f.value = data.get(f.name)

    def validate(self, data: dict[str, Any]) -> tuple[BaseModel | None, dict[str, ErrorList]]:
        cleaned_data = data.copy()
        for f in self.fields:
            if not f.required and cleaned_data.get(f.name) == "":
                cleaned_data[f.name] = None

        try:
            instance = self.model.model_validate(cleaned_data)
            self.errors = {}
            return instance, {}
        except ValidationError as e:
            errs: dict[str, ErrorList] = {}
            for error in e.errors():
                loc = error["loc"][0]
                key = str(loc)
                errs.setdefault(key, []).append(gettext_lazy(error["msg"]))
            self.errors = errs
            for f in self.fields:
                f.errors = errs.get(f.name)
            return None, errs

    @property
    def media(self) -> tuple[str, ...]:
        seen: set[str] = set()
        assets: list[str] = []
        for f in self.fields:
            for path in f.widget.static_list:
                if path not in seen:
                    seen.add(path)
                    assets.append(path)
        return tuple(assets)

    @property
    def layout_css_class(self) -> str:
        """Return the CSS class for the form layout.

        Returns ``ha-form-grid-2`` for two-column layout, empty string for single.
        """
        from hyperadmin.core.layouts import FormLayout  # noqa: PLC0415

        if self._form_layout == FormLayout.TWO_COLUMN:
            return "ha-form-grid-2"
        return ""


@dataclass(slots=True)
class InlineFormRow:
    """A single row within an inline formset.

    Attributes:
        index: The row index (0-based) within the formset.
        fields: The form fields for this row.
        pk: The primary key of an existing inline record, or ``None`` for new rows.
        delete: Whether this row is marked for deletion.
    """

    index: int
    fields: list[FormField]
    pk: int | None = None
    delete: bool = False

    @property
    def has_errors(self) -> bool:
        """Whether any field on this row carries a validation error."""
        return any(field.errors for field in self.fields)


@dataclass
class InlineFormset:
    """Manages a set of inline model rows for a parent form.

    Provides methods to build empty rows, populate from existing data,
    validate submitted data, and extract structured results.
    """

    spec: InlineModelSpec
    rows: list[InlineFormRow] = dc_field(default_factory=list)
    errors: dict[int, dict[str, ErrorList]] = dc_field(default_factory=dict)
    add_row_url: str = ""

    @property
    def prefix(self) -> str:
        """Return the form field name prefix for this inline."""
        return self.spec.model_name

    @property
    def display_fields(self) -> list[str]:
        """Return field names shown in each row."""
        return self.spec.get_display_fields()

    @property
    def field_labels(self) -> list[str]:
        """Return human-readable labels for each display field."""
        model_fields = getattr(self.spec.model, "model_fields", {})
        labels = []
        for name in self.display_fields:
            fi = model_fields.get(name)
            title = getattr(fi, "title", None) if fi else None
            labels.append(title or name.replace("_", " ").capitalize())
        return labels

    @property
    def title(self) -> str:
        return self.spec.title

    @property
    def max_num(self) -> int:
        return self.spec.max_num

    def _build_row(
        self, index: int, values: dict[str, Any] | None = None, pk: int | None = None
    ) -> InlineFormRow:
        """Build a single ``InlineFormRow`` for the given index."""
        model_fields = getattr(self.spec.model, "model_fields", {})
        vals = values or {}
        fields: list[FormField] = []
        for name in self.display_fields:
            fi = model_fields.get(name)
            if fi is None:
                continue
            widget = _pick_inline_widget(name, fi)
            value = vals.get(name)
            fields.append(FormField(name=name, model_field=fi, widget=widget, value=value))
        return InlineFormRow(index=index, fields=fields, pk=pk)

    def build_empty_rows(self, count: int | None = None) -> None:
        """Populate ``self.rows`` with empty rows.

        Args:
            count: Number of empty rows. Defaults to ``spec.extra``.
        """
        n = count if count is not None else self.spec.extra
        start = len(self.rows)
        for i in range(n):
            self.rows.append(self._build_row(start + i))

    def populate_from_instances(self, instances: list[Any]) -> None:
        """Populate rows from existing related model instances."""
        self.rows = []
        for i, inst in enumerate(instances):
            vals = inst.model_dump() if hasattr(inst, "model_dump") else {}
            pk = getattr(inst, "id", None)
            self.rows.append(self._build_row(i, values=vals, pk=pk))
        # Add extra empty rows
        self.build_empty_rows()

    def extract_submitted_data(self, form_data: Any) -> list[dict[str, Any]]:
        """Parse submitted form data into a list of row dicts.

        Form fields are named ``{prefix}-{index}-{field_name}``.
        Returns only rows that have at least one non-empty value and are not
        marked for deletion.
        """
        prefix = self.prefix
        results: list[dict[str, Any]] = []
        # Discover max index present in form data
        max_index = -1
        for key in form_data:
            if key.startswith(f"{prefix}-") and key.count("-") >= 2:
                parts = key.split("-", 2)
                try:
                    idx = int(parts[1])
                    max_index = max(max_index, idx)
                except (ValueError, IndexError):
                    pass

        for i in range(max_index + 1):
            # Check deletion flag
            delete_key = f"{prefix}-{i}-DELETE"
            if form_data.get(delete_key):
                # Collect pk for deletion
                pk_key = f"{prefix}-{i}-pk"
                pk_val = form_data.get(pk_key)
                if pk_val:
                    results.append({"_delete": True, "_pk": int(pk_val)})
                continue

            row_data: dict[str, Any] = {}
            pk_key = f"{prefix}-{i}-pk"
            pk_val = form_data.get(pk_key)
            if pk_val:
                row_data["_pk"] = int(pk_val)

            has_data = False
            for field_name in self.display_fields:
                key = f"{prefix}-{i}-{field_name}"
                val = form_data.get(key, "")
                row_data[field_name] = val
                if val not in ("", None):
                    has_data = True

            if has_data:
                results.append(row_data)

        return results

    def validate_rows(
        self,
        rows_data: list[dict[str, Any]],
        parent_pk: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[int, dict[str, ErrorList]]]:
        """Validate each row's data against the inline model.

        Returns:
            A tuple of (valid_rows, errors_by_index).
            Each valid row is a dict ready for adapter.create/update.
        """
        valid: list[dict[str, Any]] = []
        errors: dict[int, dict[str, ErrorList]] = {}

        for i, row in enumerate(rows_data):
            if row.get("_delete"):
                valid.append(row)
                continue

            # Build full data dict including FK
            data = {k: v for k, v in row.items() if not k.startswith("_")}
            if parent_pk is not None:
                data[self.spec.fk_field] = parent_pk

            # Clean empty strings to None for optional fields
            model_fields = getattr(self.spec.model, "model_fields", {})
            for field_name, val in list(data.items()):
                fi = model_fields.get(field_name)
                if fi and not fi.is_required() and val == "":
                    data[field_name] = None

            try:
                instance = self.spec.model.model_validate(data)
                result = instance.model_dump()
                if "_pk" in row:
                    result["_pk"] = row["_pk"]
                valid.append(result)
            except ValidationError as e:
                row_errors: dict[str, ErrorList] = {}
                for error in e.errors():
                    loc = str(error["loc"][0])
                    row_errors.setdefault(loc, []).append(gettext_lazy(error["msg"]))
                errors[i] = row_errors

        self.errors = errors
        return valid, errors

    def rebuild_from_submitted(self, form_data: Any) -> None:
        """Rebuild rows from submitted form data for re-rendering on validation errors."""
        prefix = self.prefix
        max_index = -1
        for key in form_data:
            if key.startswith(f"{prefix}-") and key.count("-") >= 2:
                parts = key.split("-", 2)
                try:
                    idx = int(parts[1])
                    max_index = max(max_index, idx)
                except (ValueError, IndexError):
                    pass

        self.rows = []
        for i in range(max_index + 1):
            vals: dict[str, Any] = {}
            for field_name in self.display_fields:
                key = f"{prefix}-{i}-{field_name}"
                vals[field_name] = form_data.get(key, "")

            pk_key = f"{prefix}-{i}-pk"
            pk_val = form_data.get(pk_key)
            pk = int(pk_val) if pk_val else None

            row = self._build_row(i, values=vals, pk=pk)

            # Apply field-level errors
            if i in self.errors:
                for field in row.fields:
                    field.errors = self.errors.get(i, {}).get(field.name)

            delete_key = f"{prefix}-{i}-DELETE"
            row.delete = bool(form_data.get(delete_key))

            self.rows.append(row)


def _pick_inline_widget(name: str, field_info: FieldInfo) -> HtmxWidget:
    """Pick a simple widget for an inline field (no relation support yet)."""
    ann = getattr(field_info, "annotation", None)
    origin = get_origin(ann)
    args = get_args(ann)

    if origin is not None and args and origin is Union and type(None) in args:
        ann = next(arg for arg in args if arg is not type(None))

    if ann is bool:
        return CheckboxInput()
    if ann is int:
        return NumberInput()
    if ann is float:
        return FloatInput()
    if ann is datetime:
        return DateTimeInput()
    if isinstance(ann, type) and issubclass(ann, Enum):
        return SelectInput()

    lower = name.lower()
    if lower in {"description", "text", "body", "content"}:
        return Textarea()
    return TextInput()
