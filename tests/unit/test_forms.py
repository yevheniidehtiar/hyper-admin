from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from markupsafe import Markup
from pydantic import BaseModel, Field

from hyperadmin.views.forms import (
    FormField,
    HtmxWidget,
    MultiSelectWidget,
    NumberInput,
    PydanticForm,
    RelationMultiSelectWidget,
    RelationSelectWidget,
    SelectWidget,
    Textarea,
    TextInput,
    hybrid_to_python,
    hybrid_to_storage,
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


def test_form_field_input_type_attribute_error():
    class NoName:
        pass

    field_info = MockFieldInfo(annotation=NoName())
    field = FormField(name="test_field", model_field=field_info, widget=TextInput())
    assert field.input_type == "text"


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


def test_pydantic_form_excludes_id_field():
    class ModelWithId(BaseModel):
        id: int
        name: str

    form = PydanticForm(model=ModelWithId)
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


def test_select_widget_holds_choices():
    choices = [
        {"value": "1", "label": "Option A", "selected": False},
        {"value": "2", "label": "Option B", "selected": True},
    ]
    widget = SelectWidget(choices=choices)
    assert widget.template_path == "widgets/select_input.html"
    assert widget.choices == choices


def test_select_widget_empty_by_default():
    widget = SelectWidget()
    assert widget.choices == []


def test_multiselect_widget_holds_choices():
    choices = [
        {"value": "a", "label": "Apple", "selected": True},
        {"value": "b", "label": "Banana", "selected": False},
    ]
    widget = MultiSelectWidget(choices=choices)
    assert widget.template_path == "widgets/multiselect_input.html"
    assert widget.choices == choices


def test_multiselect_widget_empty_by_default():
    widget = MultiSelectWidget()
    assert widget.choices == []


def test_hybrid_to_python_csv():
    assert hybrid_to_python("a,b,c", "csv") == ["a", "b", "c"]


def test_hybrid_to_python_json():
    assert hybrid_to_python('["x", "y"]', "json") == ["x", "y"]


def test_hybrid_to_python_list_passthrough():
    assert hybrid_to_python(["p", "q"], "csv") == ["p", "q"]


def test_hybrid_to_python_empty_string():
    assert hybrid_to_python("", "csv") == []
    assert hybrid_to_python("", "json") == []


def test_hybrid_to_storage_csv():
    assert hybrid_to_storage(["a", "b"], "csv") == "a,b"


def test_hybrid_to_storage_json():
    import json

    assert json.loads(hybrid_to_storage(["x", "y"], "json")) == ["x", "y"]


def test_hybrid_round_trip_csv():
    original = ["red", "green", "blue"]
    assert hybrid_to_python(hybrid_to_storage(original, "csv"), "csv") == original


def test_hybrid_round_trip_json():
    original = ["one", "two", "three"]
    assert hybrid_to_python(hybrid_to_storage(original, "json"), "json") == original


def test_relation_select_widget_preload():
    choices = [
        {"value": "1", "label": "UK", "selected": True},
        {"value": "2", "label": "FR", "selected": False},
    ]
    widget = RelationSelectWidget(choices_url="/city/choices/country", choices=choices)
    assert widget.template_path == "widgets/relation_select_input.html"
    assert widget.preload is True
    assert widget.choices_url == "/city/choices/country"
    assert len(widget.choices) == 2
    assert widget.choices[0]["selected"] is True


def test_relation_select_widget_lazy():
    widget = RelationSelectWidget(choices_url="/city/choices/country", preload=False)
    assert widget.preload is False
    assert widget.choices == []


def test_relation_multiselect_widget_preload():
    choices = [
        {"value": "1", "label": "London", "selected": False},
        {"value": "2", "label": "Paris", "selected": True},
    ]
    widget = RelationMultiSelectWidget(choices_url="/country/choices/cities", choices=choices)
    assert widget.template_path == "widgets/relation_multiselect_input.html"
    assert widget.preload is True
    assert len(widget.choices) == 2


def test_relation_multiselect_widget_lazy():
    widget = RelationMultiSelectWidget(choices_url="/country/choices/cities", preload=False)
    assert widget.preload is False
    assert widget.choices == []


def test_pydantic_form_media():
    class MediaWidget(HtmxWidget):
        def __init__(self):
            super().__init__(template_path="test.html", static_list=("test.css", "test.js"))

    class MediaTestModel(BaseModel):
        name: str

    form = PydanticForm(model=MediaTestModel, widgets={"name": MediaWidget()})
    assert form.media == ("test.css", "test.js")
