# Task 7: Accessibility Tests

## Overview
Implement accessibility testing for the User form, covering form roles, labeled controls, keyboard navigation, and accessibility tree validation.

## Scope
- **Scenarios Covered**: 16 from main plan
- **Estimated Time**: 30-40 minutes
- **Prerequisites**: Understanding of web accessibility standards, ARIA roles, keyboard navigation patterns

## Test Cases to Implement

### 7.1 Form Accessibility Snapshot
**File**: `test_user_form_accessibility.py::test_form_accessibility_snapshot`

**Steps**:
- Navigate to `/admin/user/create`
- Wait for page to fully load
- Capture accessibility tree snapshot
- Analyze form structure and roles

**Assertions**:
- Form element has appropriate role (form)
- All input fields are properly labeled
- Button elements are discoverable with correct names
- No missing accessibility attributes for interactive elements
- Accessibility tree contains expected form structure

### 7.2 Labeled Controls Validation
**File**: `test_user_form_accessibility.py::test_labeled_controls_validation`

**Steps**:
- Navigate to `/admin/user/create`
- Verify all form controls have proper labels
- Test label-control associations

**Assertions**:
- All required fields have visible labels: "Username", "Email", "First Name", "Last Name"
- Optional fields have visible labels: "Updated At", "Avatar", "Personal Key"
- Checkbox fields have visible labels: "Is Active", "Is Superuser"
- Labels are properly associated with their controls (for/id or implicit)
- Label text is descriptive and meaningful

### 7.3 Keyboard Navigation
**File**: `test_user_form_accessibility.py::test_keyboard_navigation`

**Steps**:
- Navigate to `/admin/user/create`
- Use Tab key to navigate through all form elements
- Test Enter/Space key activation for buttons and checkboxes
- Verify logical tab order

**Assertions**:
- All interactive elements are reachable via keyboard
- Tab order follows logical flow (top to bottom, left to right)
- Focus indicators are visible on focused elements
- Buttons can be activated with Enter or Space
- Checkboxes can be toggled with Space key
- Form can be submitted using keyboard only

### 7.4 Error Message Accessibility
**File**: `test_user_form_accessibility.py::test_error_message_accessibility`

**Steps**:
- Navigate to `/admin/user/create`
- Trigger validation errors by submitting empty required fields
- Verify error message accessibility features

**Assertions**:
- Error messages have appropriate ARIA roles (alert, error)
- Error messages are associated with their respective form fields
- Screen reader announcements work for validation errors
- Error container is properly labeled and discoverable
- Focus management during error states

## Implementation Guidelines

### Required Imports
```python
import pytest
from playwright.async_api import Page, expect
import json
```

### Test Structure
```python
@pytest.mark.asyncio
async def test_form_accessibility_snapshot(e2e_page: Page, demo_base_url: str):
    """Test form accessibility tree structure."""
    # Implementation here

@pytest.mark.asyncio
async def test_labeled_controls_validation(e2e_page: Page, demo_base_url: str):
    """Test that all form controls are properly labeled."""
    # Implementation here

@pytest.mark.asyncio
async def test_keyboard_navigation(e2e_page: Page, demo_base_url: str):
    """Test keyboard accessibility and navigation."""
    # Implementation here

@pytest.mark.asyncio
async def test_error_message_accessibility(e2e_page: Page, demo_base_url: str):
    """Test accessibility of validation error messages."""
    # Implementation here
```

### Test Data Constants
```python
# Expected form field labels
EXPECTED_LABELS = [
    "Username",
    "Email", 
    "First Name",
    "Last Name",
    "Updated At",
    "Avatar",
    "Personal Key",
    "Is Active",
    "Is Superuser"
]

# Expected button names
EXPECTED_BUTTONS = [
    "Save",
    # Optional buttons that may not be present
    # "Save and Continue",
    # "Save and Add Another"
]
```

### Accessibility Testing Patterns
```python
async def capture_and_validate_accessibility_tree(page: Page):
    """Capture accessibility snapshot and validate structure."""
    # Capture accessibility tree
    snapshot = await page.accessibility.snapshot()
    
    # Validate form structure
    form_nodes = find_nodes_by_role(snapshot, "form")
    assert len(form_nodes) > 0, "Form element should be present in accessibility tree"
    
    # Validate labeled controls
    textbox_nodes = find_nodes_by_role(snapshot, "textbox")
    checkbox_nodes = find_nodes_by_role(snapshot, "checkbox") 
    button_nodes = find_nodes_by_role(snapshot, "button")
    
    return snapshot, {
        "forms": form_nodes,
        "textboxes": textbox_nodes,
        "checkboxes": checkbox_nodes,
        "buttons": button_nodes
    }

def find_nodes_by_role(snapshot: dict, role: str) -> list:
    """Recursively find nodes with specific role in accessibility tree."""
    nodes = []
    
    def traverse(node):
        if node.get("role") == role:
            nodes.append(node)
        for child in node.get("children", []):
            traverse(child)
    
    if snapshot:
        traverse(snapshot)
    return nodes

async def validate_label_associations(page: Page, field_labels: list):
    """Validate that form fields are properly labeled."""
    for label_text in field_labels:
        # Try to find field by label
        try:
            field = page.get_by_label(label_text)
            await expect(field).to_be_visible()
            
            # Verify label is associated via for/id or implicit association
            field_id = await field.get_attribute("id")
            if field_id:
                # Check for explicit label with for attribute
                label = page.locator(f'label[for="{field_id}"]')
                label_text_content = await label.text_content() if await label.count() > 0 else None
                
                # If no explicit for/id, check for implicit label (field inside label)
                if not label_text_content:
                    implicit_label = field.locator("..").filter(has_text=label_text).first
                    assert await implicit_label.count() > 0, f"No label association found for {label_text}"
                    
        except Exception as e:
            assert False, f"Field with label '{label_text}' not accessible: {e}"
```

### Keyboard Navigation Testing
```python
async def test_keyboard_tab_order(page: Page):
    """Test logical tab order through form elements."""
    # Start from first tabbable element
    await page.keyboard.press("Tab")
    
    # Track focus order
    focus_order = []
    for i in range(20):  # Reasonable limit for form elements
        focused_element = page.locator(":focus")
        if await focused_element.count() == 0:
            break
            
        # Get element info
        tag_name = await focused_element.evaluate("el => el.tagName.toLowerCase()")
        element_type = await focused_element.get_attribute("type") or ""
        label_text = await get_associated_label_text(page, focused_element)
        
        focus_order.append({
            "tag": tag_name,
            "type": element_type,
            "label": label_text,
            "index": i
        })
        
        await page.keyboard.press("Tab")
    
    return focus_order

async def get_associated_label_text(page: Page, element) -> str:
    """Get label text for a form element."""
    # Try multiple methods to find label
    element_id = await element.get_attribute("id")
    
    if element_id:
        # Explicit label with for attribute
        label = page.locator(f'label[for="{element_id}"]')
        if await label.count() > 0:
            return await label.text_content()
    
    # Implicit label (element inside label)
    parent_label = element.locator("..").filter("label").first
    if await parent_label.count() > 0:
        return await parent_label.text_content()
    
    # Aria-label or aria-labelledby
    aria_label = await element.get_attribute("aria-label")
    if aria_label:
        return aria_label
        
    return "No label found"
```

### Error Message Accessibility
```python
async def test_validation_error_accessibility(page: Page):
    """Test accessibility of validation error messages."""
    # Trigger validation error
    await page.get_by_role("button", name="Save").click()
    
    # Wait for error messages
    error_container = page.locator("[role='alert'], .alert-danger")
    await expect(error_container).to_be_visible()
    
    # Check error message accessibility
    error_role = await error_container.get_attribute("role")
    assert error_role in ["alert", "status"], f"Error container should have alert or status role, got {error_role}"
    
    # Check if errors are announced (aria-live)
    aria_live = await error_container.get_attribute("aria-live")
    if not aria_live:
        # Should have aria-live or role=alert for announcements
        assert error_role == "alert", "Error messages should be announced to screen readers"
```

## Success Criteria
- [ ] Accessibility tree snapshot captures proper form structure
- [ ] All form controls have proper labels and associations
- [ ] Keyboard navigation works completely through the form
- [ ] Tab order is logical and intuitive
- [ ] Error messages are accessible and announced
- [ ] Focus indicators are visible and functional
- [ ] Tests pass with screen reader simulation
- [ ] File size under 150 LOC

## Dependencies
- Fixtures: `e2e_page`, `demo_base_url` from `tests/e2e/conftest.py`
- Demo app with proper accessibility implementation
- Form elements with proper ARIA roles and labels
- CSS focus indicators configured
- Error message templates with accessibility features

## Related Files
- Main plan: `tests/e2e/plans/user_form_e2e_test_plan.md`
- Fixtures: `tests/e2e/conftest.py`
- Implementation: `tests/e2e/test_user_form_accessibility.py` (to be created)
- Form templates: Check HTML templates for accessibility attributes
- Related: Task 2 (validation patterns for error accessibility)

## Notes
- Accessibility testing requires proper HTML semantics in templates
- Focus management during form submission may need special handling
- Screen reader simulation has limitations - real screen reader testing preferred
- ARIA attributes should complement, not replace, proper HTML structure
- Color contrast and visual accessibility are not covered in these automated tests
- Consider testing with different browser accessibility features enabled