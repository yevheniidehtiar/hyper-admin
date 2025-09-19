# HTMX Integration Patterns

This document outlines the best practices and patterns for integrating HTMX into Jinja2 templates within the HyperAdmin interface. Following these patterns ensures a consistent, efficient, and user-friendly experience.

## Table of Contents

- [Core Principles](#core-principles)
- [Basic HTMX Attributes](#basic-htmx-attributes)
  - [`hx-get`](#hx-get)
  - [`hx-post`](#hx-post)
  - [`hx-put`](#hx-put)
  - [`hx-patch`](#hx-patch)
  - [`hx-delete`](#hx-delete)
- [Targeting Content](#targeting-content)
  - [`hx-target`](#hx-target)
- [Swapping Content](#swapping-content)
  - [`hx-swap`](#hx-swap)
- [Triggers](#triggers)
  - [`hx-trigger`](#hx-trigger)
- [User Feedback](#user-feedback)
  - [Loading Indicators](#loading-indicators)
  - [Disabling Buttons](#disabling-buttons)
- [Common Patterns](#common-patterns)
  - [Pattern: Form Submission with Validation](#pattern-form-submission-with-validation)
  - [Pattern: Inline Editing](#pattern-inline-editing)
  - [Pattern: Deleting a Row](#pattern-deleting-a-row)
  - [Pattern: Search As You Type](#pattern-search-as-you-type)
  - [Pattern: Infinite Scroll](#pattern-infinite-scroll)
- [Error Handling](#error-handling)
- [Interoperability with Alpine.js](#interoperability-with-alpinejs)
- [Accessibility Considerations](#accessibility-considerations)

## Core Principles

1.  **Progressive Enhancement**: Start with standard HTML forms and links that work without JavaScript. Layer HTMX on top to enhance the user experience with AJAX-powered interactions. Every HTMX-enhanced feature should have a functional non-JavaScript fallback.

2.  **Server-Rendered Partials**: The server should always be the source of truth. Use HTMX to fetch HTML partials from the server. Avoid complex state management on the client.

3.  **Keep it Simple**: Prefer simple HTMX attributes over complex client-side scripting. Use Alpine.js only when necessary for interactions that are purely client-side (e.g., toggling a dropdown).

## Basic HTMX Attributes

These are the core attributes for making requests. Always prefer the specific request method attributes (`hx-post`, `hx-get`) over using `hx-request`.

### `hx-get`

Use for idempotent requests that retrieve data from the server.

**Example**: Loading content into a modal.

```html
<button
    hx-get="{{ url_for('load_content') }}"
    hx-target="#modal-content"
    class="button-primary">
    Load Content
</button>
```

### `hx-post`

Use for requests that create a new resource.

**Example**: Submitting a creation form.

```html
<form
    hx-post="{{ url_for('create_item') }}"
    hx-target="#item-list"
    hx-swap="beforeend">
    <!-- Form fields go here -->
    <button type="submit">Create</button>
</form>
```

### `hx-put` / `hx-patch`

Use for requests that update an existing resource. `hx-put` should replace the entire resource, while `hx-patch` can update a part of it.

**Example**: Updating an item.

```html
<form
    hx-put="{{ url_for('update_item', item_id=item.id) }}"
    hx-target="#item-{{ item.id }}"
    hx-swap="outerHTML">
    <!-- Form fields go here -->
    <button type="submit">Save Changes</button>
</form>
```

### `hx-delete`

Use for requests that delete a resource.

**Example**: Deleting an item from a list.

```html
<button
    hx-delete="{{ url_for('delete_item', item_id=item.id) }}"
    hx-target="closest tr"
    hx-swap="outerHTML"
    hx-confirm="Are you sure?">
    Delete
</button>
```

## Targeting Content

### `hx-target`

This attribute specifies which element will be updated with the response from the server.

-   **CSS Selector**: Use any valid CSS selector (e.g., `#my-div`, `.my-class`).
-   **`this`**: The element that triggered the request.
-   **`closest <CSS-SELECTOR>`**: The closest ancestor matching the selector.
-   **`find <CSS-SELECTOR>`**: The first descendant matching the selector.

**Good Practice**: Be as specific as possible with your targets to avoid unintended side effects.

## Swapping Content

### `hx-swap`

Determines how the new content is placed into the target element.

-   **`innerHTML` (default)**: Replaces the inner content of the target.
-   **`outerHTML`**: Replaces the entire target element.
-   **`beforeend`**: Appends the new content as the last child of the target.
-   **`afterend`**: Inserts the new content after the target element.
-   **`beforebegin`**: Inserts the new content before the target element.
-   **`afterbegin`**: Prepends the new content as the first child of the target.
-   **`none`**: Does not swap any content. Useful for requests that only trigger events.

**Good Practice**: Use `outerHTML` when updating a self-contained component (like a table row or a form) to ensure the target itself is replaced with the updated version.

## Triggers

### `hx-trigger`

Specifies the event that triggers the request.

-   **Standard events**: `click`, `submit`, `change`, `keyup`, etc.
-   **Special modifiers**:
    -   `changed`: Only trigger if the element's value has changed.
    -   `delay:<time>`: Wait for the specified time before sending (e.g., `delay:500ms`).
    -   `throttle:<time>`: Send at most one request per time interval.
    -   `from:<CSS-SELECTOR>`: Listen for the event on a different element.
-   **On load**: `load`
-   **On reveal**: `revealed`

**Example**: Search as you type.

```html
<input type="search" name="q"
    hx-get="{{ url_for('search') }}"
    hx-trigger="keyup changed delay:500ms"
    hx-target="#search-results"
>
```

## User Feedback

Providing immediate feedback is crucial for a good user experience.

### Loading Indicators

HTMX adds the `htmx-request` class to the element making a request. Use this to show loading states.

**Example**:

```html
<style>
.htmx-indicator {
    display: none;
}
.htmx-request .htmx-indicator {
    display: inline;
}
.htmx-request.htmx-indicator {
    display: inline;
}
</style>

<button hx-get="/data">
    Load Data
    <img src="/loading.gif" class="htmx-indicator">
</button>
```

For more complex scenarios, use `hx-indicator` to specify a different element to show during the request.

### Disabling Buttons

To prevent double-submissions, disable buttons during a request.

**Using CSS**:
```css
.htmx-request {
    opacity: 0.5;
    pointer-events: none;
}
```

**Using Alpine.js for more control**:
If you need to manage the `disabled` attribute, you can use Alpine.js. This will be covered in the [Interoperability with Alpine.js](#interoperability-with-alpinejs) section.

## Common Patterns

### Pattern: Form Submission with Validation

This is a critical pattern for creating and updating data.

**Scenario**: A user submits a form. If validation fails, the server re-renders the form with error messages. If it succeeds, the new/updated item is added to a list.

**The Form (`_form.html` partial)**:

```html
<form
    hx-post="{{ url_for('create_item') }}"
    hx-target="this"
    hx-swap="outerHTML"
    class="space-y-4"
>
    {% if errors %}
    <div class="alert-danger">
        <ul>
        {% for field, error_list in errors.items() %}
            {% for error in error_list %}
            <li>{{ field }}: {{ error }}</li>
            {% endfor %}
        {% endfor %}
        </ul>
    </div>
    {% endif %}

    <div>
        <label for="name">Name</label>
        <input type="text" id="name" name="name" value="{{ data.name or '' }}">
    </div>

    <button type="submit">Submit</button>
</form>
```

**The View (Python/FastAPI)**:

```python
@router.post("/items")
async def create_item(request: Request, name: str = Form(...)):
    try:
        # Validate data and create item
        new_item = create_item_in_db(name=name)

        # On success, return a partial that can be appended to the list
        # We also send a trigger to the client to close a modal, for example
        response = templates.TemplateResponse(
            "partials/item_row.html",
            {"request": request, "item": new_item},
        )
        response.headers["HX-Trigger"] = "item-created"
        return response

    except ValidationError as e:
        # On validation error, re-render the form with errors
        return templates.TemplateResponse(
            "partials/_form.html",
            {
                "request": request,
                "errors": e.errors(),
                "data": {"name": name}
            },
            status_code=422, # Unprocessable Entity
        )
```

**Key Points**:

1.  **`hx-target="this"` and `hx-swap="outerHTML"`**: The form targets itself. If validation fails, the server sends back the re-rendered form, which replaces the existing one.
2.  **Separate Success Target**: On success, the response should be handled differently. In a real app, you might target a list (`#item-list`) and use `hx-swap="beforeend"`. This can be achieved by returning a different `HX-Retarget` header from the server on success.
3.  **HTTP Status Codes**: Return a `422` status code for validation errors. This is semantically correct and can be used by HTMX for client-side error handling if needed.

### Pattern: Inline Editing

**Scenario**: A user clicks an "Edit" button. The content is replaced by a form. Submitting the form saves the data and replaces the form with the updated content.

**Initial View (`_item_view.html`)**:

```html
<div id="item-{{ item.id }}" hx-target="this">
    <span>{{ item.name }}</span>
    <button
        hx-get="{{ url_for('get_edit_form', item_id=item.id) }}"
        hx-swap="outerHTML"
        class="button-secondary">
        Edit
    </button>
</div>
```

**Edit Form (`_item_edit.html`)**:

```html
<form
    id="item-{{ item.id }}"
    hx-put="{{ url_for('update_item', item_id=item.id) }}"
    hx-target="this"
    hx-swap="outerHTML"
>
    <input type="text" name="name" value="{{ item.name }}">
    <button type="submit">Save</button>
    <button hx-get="{{ url_for('get_item_view', item_id=item.id) }}">Cancel</button>
</form>
```

**The View (Python/FastAPI)**:

The Python views would handle:
1.  A `GET` request to `get_edit_form` which returns the `_item_edit.html` partial.
2.  A `PUT` request to `update_item` which, on success, returns the `_item_view.html` partial for the updated item. On failure, it re-renders the `_item_edit.html` form with errors.
3.  A `GET` request to `get_item_view` for the "Cancel" button, which returns the original `_item_view.html` partial.

### Pattern: Deleting a Row

This is a straightforward but common pattern.

**The List View**:

```html
<table>
    <tbody id="item-list">
        {% for item in items %}
        <tr id="item-row-{{ item.id }}">
            <td>{{ item.name }}</td>
            <td>
                <button
                    hx-delete="{{ url_for('delete_item', item_id=item.id) }}"
                    hx-target="#item-row-{{ item.id }}"
                    hx-swap="outerHTML"
                    hx-confirm="Are you sure you want to delete this item?">
                    Delete
                </button>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

**The View (Python/FastAPI)**:

```python
@router.delete("/items/{item_id}")
async def delete_item(item_id: int):
    # Perform deletion in the database
    delete_item_from_db(item_id)
    # Return an empty response with status 200 OK
    # HTMX will then swap the target as requested.
    return Response(status_code=200)
```

**Key Points**:

-   **`hx-target`**: Targets the closest `tr` or a specific ID for the row.
-   **`hx-swap="outerHTML"`**: Removes the entire row from the DOM.
-   **`hx-confirm`**: A simple and effective way to ask for user confirmation.

### Pattern: Search As You Type

**The Input**:

```html
<input
    type="search"
    name="q"
    hx-post="{{ url_for('search_items') }}"
    hx-trigger="keyup changed delay:300ms, search"
    hx-target="#search-results"
    hx-indicator=".htmx-indicator"
    placeholder="Search for items..."
>
<div id="search-results">
    <!-- Results will be loaded here -->
</div>
```

**The View (Python/FastAPI)**:

The `search_items` view would take the search query, find matching items, and return an HTML partial containing the list of results.

### Pattern: Infinite Scroll

**The Trigger Element**:

```html
<div
    hx-get="{{ url_for('get_next_page', page=2) }}"
    hx-trigger="revealed"
    hx-swap="afterend"
>
    <!-- The next page of items will be inserted here -->
</div>
```

**The View (Python/FastAPI)**:

The `get_next_page` view would:
1.  Fetch the requested page of items.
2.  Render a partial containing the items for that page.
3.  Include a new trigger element in its response with the URL for the *next* page (e.g., `page=3`).

## Error Handling

-   **Server Errors (5xx)**: These are unrecoverable from the client's perspective. The default HTMX behavior (showing an error in the console) is often sufficient. You can customize this by listening for the `htmx:responseError` event.
-   **Client Errors (4xx)**: For validation errors (`422`), the pattern of re-rendering the form with error messages is the recommended approach. For other 4xx errors (e.g., `403 Forbidden`, `404 Not Found`), you can either let HTMX handle them or create a custom error display mechanism.

## Interoperability with Alpine.js

While HTMX handles server interactions, Alpine.js is excellent for purely client-side behaviors.

**Events**:
-   Use `HX-Trigger` response headers from the server to dispatch events that Alpine can listen to.
-   Use `htmx.trigger()` in JavaScript to dispatch events from Alpine to HTMX.

**Example**: A modal that is controlled by Alpine, but its content is loaded by HTMX.

```html
<!-- The Alpine-controlled modal -->
<div x-data="{ open: false }" @item-created.window="open = false">
    <button @click="open = true">Open Modal</button>

    <div x-show="open" class="modal">
        <div id="modal-content">
            <!-- Content loaded by HTMX will go here -->
        </div>
        <button @click="open = false">Close</button>
    </div>
</div>

<!-- The form that loads content and triggers the event -->
<form
    hx-post="/items"
    hx-target="#item-list"
    hx-swap="beforeend"
>
    <!-- On success, the server responds with HX-Trigger: item-created -->
</form>
```

## Accessibility Considerations

-   **Focus Management**: After an element is swapped, the focus is lost. Use the `hx-swap` `focus-scroll:true` extension or custom JavaScript to manage focus appropriately, especially in forms.
-   **ARIA Attributes**: Use ARIA attributes (`aria-busy`, `aria-live`) to inform screen reader users about dynamic content changes. For example, mark a target region with `aria-live="polite"` so that its updates are announced.

This document provides a foundation. As the project evolves, new patterns may emerge and should be documented here.
