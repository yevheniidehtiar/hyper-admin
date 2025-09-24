from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Union, get_args, get_origin

from markupsafe import Markup
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo
from starlette.templating import Jinja2Templates


@dataclass(slots=True)
class HtmxWidget:
    """A minimal widget abstraction capable of rendering via a Jinja template.

    template_path: path to template included under the project templates directory.
    static_list: optional JS/CSS assets to include once per page.
    htmx_attrs: optional HTMX attributes to include on the input element.
    """

    template_path: str
    static_list: tuple[str, ...] = ()
    htmx_attrs: Mapping[str, str] | None = None

    def render(self, templates: Jinja2Templates, form_field: FormField, request) -> Markup:
        context = {
            "request": request,
            "field": form_field,
            "widget": self,
        }
        return Markup(templates.get_template(self.template_path).render(context))


class TextInput(HtmxWidget):
    def __init__(self):
        super().__init__(template_path="widgets/text_input.html")


class NumberInput(HtmxWidget):
    def __init__(self):
        super().__init__(template_path="widgets/number_input.html")


class FloatInput(HtmxWidget):
    def __init__(self):
        super().__init__(template_path="widgets/float_input.html")


class Textarea(HtmxWidget):
    def __init__(self):
        super().__init__(template_path="widgets/textarea.html")


class CheckboxInput(HtmxWidget):
    def __init__(self):
        super().__init__(template_path="widgets/checkbox_input.html")


class SelectInput(HtmxWidget):
    def __init__(self):
        super().__init__(template_path="widgets/select_input.html")


class DateTimeInput(HtmxWidget):
    def __init__(self):
        super().__init__(template_path="widgets/datetime_input.html")


@dataclass(slots=True)
class FormField:
    name: str
    model_field: FieldInfo
    widget: HtmxWidget
    value: Any | None = None
    errors: list[str] | None = None

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


class PydanticForm:
    def __init__(
        self,
        model: type[BaseModel],
        *,
        widgets: dict[str, HtmxWidget] | None = None,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        initial: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.widgets = widgets or {}
        self.include = set(include or [])
        self.exclude = set(exclude or [])
        self.initial = initial or {}
        self.errors: dict[str, list[str]] = {}
        self._fields: list[FormField] = []

    def _pick_widget(self, name: str, field: FieldInfo) -> HtmxWidget:
        if name in self.widgets:
            return self.widgets[name]
        # Heuristics for common fields
        lower = name.lower()
        if lower in {"description", "text", "body", "content"}:
            return Textarea()

        ann = getattr(field, "annotation", None)
        origin = get_origin(ann)
        args = get_args(ann)

        if origin is not None and args:
            # Handle Optional[T]
            if origin is Union and type(None) in args:
                ann = next(arg for arg in args if arg is not type(None))

        if ann == bool:
            return CheckboxInput()
        if ann == int:
            return NumberInput()
        if ann == float:
            return FloatInput()
        if ann == datetime:
            return DateTimeInput()
        if isinstance(ann, type) and issubclass(ann, Enum):
            return SelectInput()
        return TextInput()

    @staticmethod
    def _is_auto_now_field(field: FieldInfo) -> bool:
        if isinstance(field, FieldInfo):
            sa_column_kwargs = getattr(field, "sa_column_kwargs", None)
            if sa_column_kwargs and isinstance(sa_column_kwargs, dict):
                if "server_default" in sa_column_kwargs or "onupdate" in sa_column_kwargs:
                    return True
            if field.default_factory == datetime.now:
                return True
        return False

    @property
    def fields(self) -> list[FormField]:
        if self._fields:
            return self._fields
        for name, field in self.model.model_fields.items():
            if self.include and name not in self.include:
                continue
            if name in self.exclude:
                continue
            # Exclude common primary key name by default for create/update forms
            if name == "id":
                continue
            if self._is_auto_now_field(field):
                continue
            widget = self._pick_widget(name, field)
            # Pydantic FieldInfo.default may be PydanticUndefined; use None in that case
            default_val = getattr(field, "default", None)
            if str(default_val) == "PydanticUndefined":
                default_val = None
            value = self.initial.get(name, default_val if default_val is not None else None)
            self._fields.append(FormField(name=name, model_field=field, widget=widget, value=value))
        return self._fields

    def bind(self, data: dict[str, Any]) -> None:
        for f in self.fields:
            f.value = data.get(f.name, None)

    def validate(self, data: dict[str, Any]) -> tuple[BaseModel | None, dict[str, list[str]]]:
        cleaned_data = data.copy()
        for f in self.fields:
            if not f.required and cleaned_data.get(f.name) == "":
                cleaned_data[f.name] = None

        try:
            instance = self.model.model_validate(cleaned_data)
            self.errors = {}
            return instance, {}
        except ValidationError as e:
            errs: dict[str, list[str]] = {}
            for error in e.errors():
                loc = error["loc"][0]
                key = str(loc)
                errs.setdefault(key, []).append(error["msg"])
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
