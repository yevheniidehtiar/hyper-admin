{% raw %}
# Widgets

A **widget** controls how a single form field is rendered as HTML and what HTMX attributes, if any, it carries. Widgets are Python dataclasses that pair a Jinja2 template with optional static assets and HTMX attributes.

---

## Widget Architecture

```python
@dataclass(slots=True)
class HtmxWidget:
    template_path: str                        # Jinja2 template to render
    static_list: tuple[str, ...] = ()         # CSS/JS assets to include
    htmx_attrs: Mapping[str, str] | None = None  # hx-* attributes injected into the element
```

Every widget template receives a `FormField` context object:

```python
@dataclass(slots=True)
class FormField:
    name: str                   # HTML name attribute
    model_field: FieldInfo      # Pydantic FieldInfo (metadata, annotation)
    widget: HtmxWidget
    value: Any | None = None    # Current value (for edit forms)
    errors: list[str] | None = None

    @property
    def label(self) -> str: ...      # Human-readable label
    @property
    def required(self) -> bool: ...  # Whether the field is required
    @property
    def help_text(self) -> str | None: ...  # Field description
```

### Standard HTML Structure

All widgets follow the same outer wrapper pattern:

```html
<div class="ha-form-group">
    <label for="{{ field.name }}" class="ha-label">
        {{ field.label }}
        {%- if field.required -%}<span class="ha-required">*</span>{%- endif -%}
    </label>

    <!-- widget-specific input element -->

    {%- if field.help_text -%}
        <p class="ha-help-text">{{ field.help_text }}</p>
    {%- endif -%}
    {%- if field.errors -%}
        <ul class="ha-field-errors" aria-live="polite">
            {%- for e in field.errors -%}<li>{{ e }}</li>{%- endfor -%}
        </ul>
    {%- endif -%}
</div>
```

---

## Built-in Widgets

### Auto-selection Logic

`PydanticForm` picks a widget automatically based on the field's Python type annotation and name. Override by passing `widgets={"field_name": MyWidget()}` to `PydanticForm`.

| Condition | Widget selected |
|---|---|
| Field name is `description`, `text`, `body`, or `content` | `Textarea` |
| Annotation is `bool` | `CheckboxInput` |
| Annotation is `int` | `NumberInput` |
| Annotation is `float` | `FloatInput` |
| Annotation is `datetime` | `DateTimeInput` |
| Annotation is an `Enum` subclass | `SelectInput` |
| Anything else | `TextInput` |

### TextInput

Renders `<input type="text">`. Suitable for short strings.

```html
<input id="{{ field.name }}" name="{{ field.name }}"
       type="text" value="{{ field.value or '' }}"
       class="ha-input"
       aria-invalid="{{ 'true' if field.errors else 'false' }}" />
```

### NumberInput / FloatInput

Both render `<input type="number">`. `FloatInput` adds `step="any"` to allow decimals.

### Textarea

Renders `<textarea>`. Auto-selected for fields whose name implies long-form text.

### CheckboxInput

Renders a checkbox where the label wraps the input (label-as-container pattern for larger click targets):

```html
<label for="{{ field.name }}" class="ha-checkbox-label">
    <input type="checkbox" id="{{ field.name }}" name="{{ field.name }}"
           value="true" class="ha-checkbox"
           {%- if field.value -%}checked{%- endif -%} />
    <span class="ha-checkbox-text">{{ field.label }}</span>
</label>
```

### SelectInput

Renders `<select>` for `Enum` fields. Iterates over enum members to produce options:

```html
<select id="{{ field.name }}" name="{{ field.name }}" class="ha-select"
        aria-invalid="{{ 'true' if field.errors else 'false' }}">
    {%- for choice in field.model_field.annotation -%}
        <option value="{{ choice.value }}"
                {%- if choice == field.value -%}selected{%- endif -%}>
            {{ choice.name }}
        </option>
    {%- endfor -%}
</select>
```

### DateTimeInput

Renders `<input type="datetime-local">`.

---

## Future Widgets

The following widgets do not yet exist. They are design specifications for planned additions. All approaches are HTMX-native — no select2, Choices.js, or other JavaScript libraries.

### DependentSelectWidget (Cascading Selects)

**Use case:** The available options for field B depend on the current value of field A. Example: Country → State → City, or Category → Subcategory.

**Approach:** The parent `<select>` carries `hx-get` pointing to a server endpoint that returns only the child `<select>` HTML. The endpoint reads the parent's submitted value via `hx-include`.

#### Template (`widgets/dependent_select_input.html`)

```html
<div class="ha-form-group">
    <label for="{{ field.name }}" class="ha-label">
        {{ field.label }}
        {%- if field.required -%}<span class="ha-required">*</span>{%- endif -%}
    </label>
    <select id="{{ field.name }}" name="{{ field.name }}"
            class="ha-select"
            aria-invalid="{{ 'true' if field.errors else 'false' }}"
            hx-get="{{ widget.options_url }}"
            hx-trigger="change"
            hx-target="#{{ widget.target_id }}"
            hx-include="[name='{{ field.name }}']">
        <option value="">— select —</option>
        {%- for choice in field.choices -%}
            <option value="{{ choice.value }}"
                    {%- if choice.value == field.value -%}selected{%- endif -%}>
                {{ choice.label }}
            </option>
        {%- endfor -%}
    </select>
    {%- if field.errors -%}
        <ul class="ha-field-errors" aria-live="polite">
            {%- for e in field.errors -%}<li>{{ e }}</li>{%- endfor -%}
        </ul>
    {%- endif -%}
</div>
```

The child field renders into a container `<div id="{{ widget.target_id }}">`:

```html
<!-- rendered by the child's DependentSelectWidget template -->
<div class="ha-form-group" id="subcategory-container">
    <label for="subcategory" class="ha-label">Subcategory</label>
    <select id="subcategory" name="subcategory" class="ha-select">
        <option value="">— select category first —</option>
        {%- for choice in choices -%}
            <option value="{{ choice.value }}">{{ choice.label }}</option>
        {%- endfor -%}
    </select>
</div>
```

#### Widget class (planned)

```python
@dataclass(slots=True)
class DependentSelectWidget(HtmxWidget):
    template_path: str = "widgets/dependent_select_input.html"
    options_url: str = ""     # e.g. "/admin/subcategory-options"
    target_id: str = ""       # e.g. "subcategory-container"
```

#### Server endpoint contract

The endpoint receives the parent value as a query parameter and returns an HTML partial containing the child `<div class="ha-form-group">`. It must be registered on the admin app separately from the CRUD routes.

```python
@router.get("/admin/subcategory-options")
async def subcategory_options(category: str, request: Request):
    choices = get_subcategories_for(category)
    return templates.TemplateResponse(
        "widgets/dependent_select_input_options.html",
        {"request": request, "choices": choices},
    )
```

**No JavaScript is required.** The entire cascade is driven by the `change` event on the parent select.

---

### MultiSelectWidget (Searchable Checkbox List)

**Use case:** A field accepts multiple values from a fixed or semi-dynamic option set. Examples: tags, permissions, categories assigned to a product.

**Approach:** Render a searchable panel of checkboxes. Each checkbox has the same `name` attribute; the form submission sends multiple values for that name. HTMX fetches filtered options from the server as the user types; Alpine.js manages the open/close state of the panel and renders selected-item chips.

This avoids `<select multiple>` (which has poor cross-browser UX) and select2 (which adds a jQuery dependency).

#### HTML structure

```html
<div class="ha-form-group">
    <label class="ha-label">
        {{ field.label }}
        {%- if field.required -%}<span class="ha-required">*</span>{%- endif -%}
    </label>

    <div class="ha-multiselect"
         x-data="haMultiselect({{ field.value | tojson }})"
         role="group"
         aria-label="{{ field.label }}">

        <!-- Selected chips + trigger -->
        <div class="ha-multiselect-trigger"
             @click="open = !open"
             :aria-expanded="open">
            <template x-for="item in selected" :key="item.value">
                <span class="ha-multiselect-chip">
                    <span x-text="item.label"></span>
                    <button type="button"
                            class="ha-multiselect-chip-remove"
                            @click.stop="deselect(item)"
                            :aria-label="'Remove ' + item.label">×</button>
                    <!-- Hidden input carries the value on form submit -->
                    <input type="hidden" :name="'{{ field.name }}'" :value="item.value">
                </span>
            </template>
            <span class="ha-multiselect-placeholder"
                  x-show="selected.length === 0">Select…</span>
        </div>

        <!-- Dropdown panel -->
        <div class="ha-multiselect-dropdown"
             x-show="open"
             @click.outside="open = false"
             x-transition>

            <input type="search"
                   class="ha-search-input"
                   placeholder="Search…"
                   hx-get="{{ widget.options_url }}"
                   hx-trigger="keyup changed delay:300ms, search"
                   hx-target="#{{ field.name }}-options"
                   hx-include="this"
                   @keydown.escape="open = false" />

            <div id="{{ field.name }}-options"
                 class="ha-multiselect-options"
                 role="listbox"
                 aria-multiselectable="true">
                {%- for choice in field.choices -%}
                    <label class="ha-multiselect-option"
                           role="option"
                           :aria-selected="isSelected('{{ choice.value }}')">
                        <input type="checkbox"
                               class="ha-checkbox"
                               value="{{ choice.value }}"
                               :checked="isSelected('{{ choice.value }}')"
                               @change="toggle({ value: '{{ choice.value }}', label: '{{ choice.label }}' })" />
                        <span>{{ choice.label }}</span>
                    </label>
                {%- endfor -%}
            </div>
        </div>
    </div>

    {%- if field.errors -%}
        <ul class="ha-field-errors" aria-live="polite">
            {%- for e in field.errors -%}<li>{{ e }}</li>{%- endfor -%}
        </ul>
    {%- endif -%}
</div>
```

#### Alpine.js component (minimal, in `hyperadmin.css` bundle or inline)

```javascript
function haMultiselect(initialValues) {
    return {
        open: false,
        selected: initialValues || [],   // [{ value, label }, ...]
        isSelected(value) {
            return this.selected.some(s => s.value === value);
        },
        toggle(item) {
            if (this.isSelected(item.value)) {
                this.deselect(item);
            } else {
                this.selected.push(item);
            }
        },
        deselect(item) {
            this.selected = this.selected.filter(s => s.value !== item.value);
        },
    };
}
```

#### CSS additions (planned for `hyperadmin.css`)

```css
.ha-multiselect { position: relative; }
.ha-multiselect-trigger {
    display: flex; flex-wrap: wrap; gap: var(--ha-space-1);
    min-height: 2.5rem; padding: var(--ha-space-2);
    border: var(--ha-border-width) solid var(--ha-color-border);
    border-radius: var(--ha-radius-lg);
    background: var(--ha-color-surface);
    cursor: pointer;
}
.ha-multiselect-chip {
    display: inline-flex; align-items: center; gap: var(--ha-space-1);
    padding: 0 var(--ha-space-2);
    background: var(--ha-color-primary-light);
    color: var(--ha-color-primary);
    border-radius: var(--ha-radius);
    font-size: var(--ha-font-size-sm);
}
.ha-multiselect-chip-remove {
    background: none; border: none;
    color: inherit; cursor: pointer; font-size: 1rem; line-height: 1;
}
.ha-multiselect-dropdown {
    position: absolute; top: 100%; left: 0; right: 0; z-index: 20;
    background: var(--ha-color-surface);
    border: var(--ha-border-width) solid var(--ha-color-border);
    border-radius: var(--ha-radius-lg);
    box-shadow: var(--ha-shadow-md);
    max-height: 18rem; overflow-y: auto;
    padding: var(--ha-space-2);
}
.ha-multiselect-options { display: flex; flex-direction: column; gap: var(--ha-space-1); }
.ha-multiselect-option {
    display: flex; align-items: center; gap: var(--ha-space-2);
    padding: var(--ha-space-2);
    border-radius: var(--ha-radius);
    cursor: pointer;
}
.ha-multiselect-option:hover { background: var(--ha-color-bg); }
```

#### Widget class (planned)

```python
@dataclass(slots=True)
class MultiSelectWidget(HtmxWidget):
    template_path: str = "widgets/multiselect_input.html"
    options_url: str = ""    # endpoint that returns filtered option list HTML
```

#### Server endpoint contract

The options endpoint accepts a `search` query parameter and returns an HTML partial of `<label class="ha-multiselect-option">` elements only (not the full panel). HTMX replaces `#field-name-options` with this partial.

```python
@router.get("/admin/tag-options")
async def tag_options(search: str = "", request: Request = ...):
    matches = filter_tags(search)
    return templates.TemplateResponse(
        "widgets/multiselect_options.html",
        {"request": request, "choices": matches},
    )
```

**Form submission** works with standard HTML: multiple `<input type="hidden" name="tags">` elements are submitted together. Pydantic reads `list[str]` naturally from repeated form keys.

---

## Design Constraints for Future Widgets

These constraints apply to any new widget added to HyperAdmin:

1. **No external JS libraries.** Use HTMX for server round-trips and Alpine.js (already loaded) for local state. Do not add jQuery, select2, Choices.js, Flatpickr, or similar.

2. **Server renders options.** Option lists come from the server as HTML. The client never builds HTML from JSON.

3. **Standard form submission.** Widgets must submit their values as ordinary HTML form fields (`<input>`, `<select>`, `<textarea>`). Pydantic validation on the server is the only validation layer that matters.

4. **CSS tokens only.** New CSS classes must use `ha-*` prefix and refer to existing custom properties. No new hard-coded colours or sizes.

5. **Accessible by default.** Every interactive element needs a label, appropriate ARIA role, and keyboard navigation.

6. **Progressive enhancement.** Where possible, the widget must function (at minimum, submit a value) without JavaScript.
{% endraw %}
