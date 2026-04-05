---
type: story
id: ttuFml_gOFR9
title: "feat(views): create FileInputWidget with basic file input"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - area:templates
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 391
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:49edc7619ac6a2c068d1ed3242383d3cae748b6f2ce42b06d034fed8e4a1dc22
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T21:12:30Z
updated_at: 2026-04-01T20:57:01Z
---

## Context

Adds `FileInputWidget` to the widget system so file/image fields render as `<input type="file">`. Follows the existing `HtmxWidget` dataclass pattern. Widget selection (`_pick_widget()`) is extended to return `FileInputWidget` when `classify_field()` returns `FileFieldMeta`.

**Spec**: `docs/specs/file-uploads.md`
**Depends on**: #387 (SDD approval), #389

## Scenarios

**Scenario: _pick_widget returns FileInputWidget for FileFieldMeta**
  Given a field classified as `FileFieldMeta(field_type="file")`
  When  `PydanticForm._pick_widget(field_name, field_info)` is called
  Then  a `FileInputWidget` instance is returned

**Scenario: file input renders with correct attributes**
  Given a model with a `FileType` column `document`
  When  the create form page is rendered
  Then  an `<input type="file" name="document">` is present
  And   the input has `aria-label` matching the field label

**Scenario: file input shows current filename on edit form**
  Given an existing record with `document="report.pdf"`
  When  the edit form is rendered
  Then  the text "report.pdf" is displayed near the file input
  And   a file input for replacement is shown below it

## Acceptance Criteria

- [ ] `FileInputWidget(HtmxWidget)` class in `src/hyperadmin/views/forms.py` with `template_path="widgets/file_input.html"`, `input_type: ClassVar[str] = "file"`
- [ ] `FileInputWidget` accepts `allowed_types: list[str] = field(default_factory=list)` and `max_size: int = 10_000_000` for client-side `accept` attribute
- [ ] `src/hyperadmin/templates/widgets/file_input.html` created using `field_wrapper` macro from `components/_macros.html`
- [ ] Template renders `<input type="file" id="{{ field.name }}" name="{{ field.name }}" accept="{{ widget.accept_attr }}" data-testid="file-input-{{ field.name }}">`
- [ ] Template shows current filename if `field.value` is set (edit mode)
- [ ] `_pick_widget()` in `PydanticForm` returns `FileInputWidget` when `classify_field()` returns `FileFieldMeta`
- [ ] Unit tests for widget selection and template rendering

## Files Likely Affected

- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/templates/widgets/file_input.html` (new)
- `tests/unit/test_file_widget.py` (new)

## Notes for Implementer

- Follow `TextInput` as a reference: same dataclass pattern, same `field_wrapper` macro usage
- `slots=True` on the dataclass — extra attributes use `object.__setattr__` pattern (see `RelationSelectWidget` for example)
- `accept_attr` property: join `allowed_types` with comma: `",".join(self.allowed_types)` or `""` for unrestricted
- Template must be under 30 lines
