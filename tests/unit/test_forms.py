from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from markupsafe import Markup
from pydantic import BaseModel, Field

from hyperadmin.views.forms import (
    FormField,
    HtmxWidget,
    NumberInput,
    PydanticForm,
    Textarea,
    TextInput,
)


@dataclass
class MockFieldInfo:
    title: str | None = None
    description: str | None = None
    is_required: bool = False
    annotation: Any = None
    default: Any = None


def test_htmx_widget_render():
    class MockTemplates:
        def get_template(self, template_path):
            class MockTemplate:
                def render(self, context):
                    return f"rendered {template_path} with {context['field'].name}"

            return MockTemplate()

    widget = HtmxWidget(template_path="test.html")
    field = FormField(name="test_field", model_field=MockFieldInfo(), widget=widget)
    rendered = widget.render(MockTemplates(), field, {})
    assert isinstance(rendered, Markup)
    assert str(rendered) == "rendered test.html with test_field"


def test_form_field_properties():
    field_info = MockFieldInfo(
        title="Test Title", description="Test help text", is_required=True, annotation=int
    )
    field = FormField(name="test_field", model_field=field_info, widget=TextInput())

    assert field.label == "Test Title"
    assert field.required is True
    assert field.help_text == "Test help text"
    assert field.input_type == "int"


def test_form_field_label_fallback():
    field_info = MockFieldInfo()
    field = FormField(name="test_field", model_field=field_info, widget=TextInput())
    assert field.label == "Test field"


class PydanticModel(BaseModel):
    name: str = Field(title="Name")
    age: int = Field(title="Age")
    bio: str | None = Field(None, title="Biography")


def test_pydantic_form_fields():
    form = PydanticForm(model=PydanticModel)
    assert len(form.fields) == 3
    assert form.fields[0].name == "name"
    assert form.fields[1].name == "age"
    assert form.fields[2].name == "bio"


def test_pydantic_form_include_exclude():
    form = PydanticForm(model=PydanticModel, include=["name"], exclude=["age"])
    assert len(form.fields) == 1
    assert form.fields[0].name == "name"


def test_pydantic_form_pick_widget():
    class WidgetTestModel(BaseModel):
        description: str
        age: int
        name: str

    form = PydanticForm(model=WidgetTestModel)
    fields = {f.name: f for f in form.fields}
    assert isinstance(fields["description"].widget, Textarea)
    assert isinstance(fields["age"].widget, NumberInput)
    assert isinstance(fields["name"].widget, TextInput)


def test_pydantic_form_bind_and_validate():
    form = PydanticForm(model=PydanticModel)
    data = {"name": "Test", "age": "30"}
    form.bind(data)
    assert form.fields[0].value == "Test"
    assert form.fields[1].value == "30"

    instance, errors = form.validate(data)
    assert instance is not None
    assert not errors
    assert instance.name == "Test"
    assert instance.age == 30


def test_pydantic_form_validation_error():
    form = PydanticForm(model=PydanticModel)
    data = {"name": "Test"}
    instance, errors = form.validate(data)
    assert instance is None
    assert "age" in errors


def test_pydantic_form_media():
    class MediaWidget(HtmxWidget):
        def __init__(self):
            super().__init__(template_path="test.html", static_list=("test.css", "test.js"))

    class MediaTestModel(BaseModel):
        name: str

    form = PydanticForm(model=MediaTestModel, widgets={"name": MediaWidget()})
    assert form.media == ("test.css", "test.js")
