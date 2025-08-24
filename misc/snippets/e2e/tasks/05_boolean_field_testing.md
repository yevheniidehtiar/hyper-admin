# Task 5: Boolean Field Tests

## Overview
Implement boolean checkbox field testing for the User form's "Is Active" and "Is Superuser" fields, focusing on toggle persistence and state management.

## Scope
- **Scenarios Covered**: 12 from main plan
- **Estimated Time**: 20-30 minutes
- **Prerequisites**: Understanding of checkbox input handling, form state persistence

## Test Cases to Implement

### 5.1 Boolean Toggle Persistence
**File**: `test_user_form_booleans.py::test_boolean_toggle_persistence`

**Steps**:
- Navigate to `/admin/user/create`
- Fill all required fields with valid values
- Toggle "Is Active" to unchecked (may be checked by default)
- Toggle "Is Superuser" to checked (likely unchecked by default)
- Click "Save" button
- Wait for successful redirect
- Navigate to edit page of the created user

**Assertions**:
- User creation succeeds (redirect to list page)
- Navigate to edit page for the created user
- "Is Active" checkbox is unchecked (state persisted)
- "Is Superuser" checkbox is checked (state persisted)
- Boolean values properly saved and retrieved from database

### 5.2 Default Boolean States
**File**: `test_user_form_booleans.py::test_default_boolean_states`

**Steps**:
- Navigate to `/admin/user/create`
- Observe default checkbox states without clicking them

**Assertions**:
- "Is Active" has expected default state (likely checked)
- "Is Superuser" has expected default state (likely unchecked)
- Default states are consistent with model definitions
- Checkboxes are properly labeled and accessible

### 5.3 Boolean State After Validation Error
**File**: `test_user_form_booleans.py::test_boolean_state_after_validation_error`

**Steps**:
- Navigate to `/admin/user/create`
- Toggle "Is Active" to unchecked and "Is Superuser" to checked
- Leave required fields (Username, Email) empty to trigger validation error
- Click "Save" button
- Observe form state after validation error

**Assertions**:
- Server returns 422 status code
- Validation error alert block visible
- "Is Active" remains unchecked (state preserved)
- "Is Superuser" remains checked (state preserved)
- Boolean field states are preserved through validation errors

## Implementation Guidelines

### Required Imports
```python
import pytest
from playwright.async_api import Page, expect
```

### Test Structure
```python
@pytest.mark.asyncio
async def test_boolean_toggle_persistence(e2e_page: Page, demo_base_url: str):
    """Test that boolean checkbox states persist after save and reload."""
    # Implementation here

@pytest.mark.asyncio
async def test_default_boolean_states(e2e_page: Page, demo_base_url: str):
    """Test default states of boolean checkboxes."""
    # Implementation here

@pytest.mark.asyncio
async def test_boolean_state_after_validation_error(e2e_page: Page, demo_base_url: str):
    """Test that boolean states are preserved after validation errors."""
    # Implementation here
```

### Test Data Constants
```python
# Base user data for boolean tests
BOOLEAN_USER_BASE = {
    "username": "test_user_boolean_001",
    "email": "boolean_test+001@example.com",
    "first_name": "Boolean",
    "last_name": "Test"
}

# Expected default states (adjust based on model defaults)
EXPECTED_DEFAULTS = {
    "is_active": True,      # Likely checked by default
    "is_superuser": False   # Likely unchecked by default
}
```

### Key Selectors
```python
# Checkbox selectors
IS_ACTIVE_CHECKBOX = 'input[name="is_active"], page.get_by_label("Is Active")'
IS_SUPERUSER_CHECKBOX = 'input[name="is_superuser"], page.get_by_label("Is Superuser")'

# Alternative selectors if labels differ
# page.locator('input[type="checkbox"][name="is_active"]')
# page.locator('input[type="checkbox"][name="is_superuser"]')
```

### Helper Functions
```python
async def get_checkbox_state(page: Page, checkbox_label: str) -> bool:
    """Get the current checked state of a checkbox."""
    checkbox = page.get_by_label(checkbox_label)
    return await checkbox.is_checked()

async def set_checkbox_state(page: Page, checkbox_label: str, checked: bool):
    """Set checkbox to specific state (checked/unchecked)."""
    checkbox = page.get_by_label(checkbox_label)
    current_state = await checkbox.is_checked()
    
    if current_state != checked:
        await checkbox.click()

async def fill_required_fields_only(page: Page, user_data: dict):
    """Fill only the required fields for testing boolean persistence."""
    await page.get_by_label("Username").fill(user_data["username"])
    await page.get_by_label("Email").fill(user_data["email"])
    await page.get_by_label("First Name").fill(user_data["first_name"])
    await page.get_by_label("Last Name").fill(user_data["last_name"])

async def create_user_and_get_edit_url(page: Page, base_url: str, user_data: dict) -> str:
    """Create user and return edit page URL for verification."""
    # Submit form, wait for redirect, extract user ID
    # Return edit URL for the created user
```

### Checkbox State Verification Pattern
```python
# Verify checkbox states
async def assert_checkbox_states(page: Page, is_active: bool, is_superuser: bool):
    """Assert specific checkbox states."""
    active_state = await get_checkbox_state(page, "Is Active")
    superuser_state = await get_checkbox_state(page, "Is Superuser")
    
    assert active_state == is_active, f"Is Active should be {is_active}, got {active_state}"
    assert superuser_state == is_superuser, f"Is Superuser should be {is_superuser}, got {superuser_state}"
```

## Success Criteria
- [ ] Boolean toggle persistence test passes consistently
- [ ] Default boolean states verified and documented
- [ ] Boolean states preserved through validation errors
- [ ] Tests use accessible checkbox selectors
- [ ] Checkbox state checking is reliable and consistent
- [ ] File size under 150 LOC
- [ ] Tests are independent and use unique test data

## Dependencies
- Fixtures: `e2e_page`, `demo_base_url` from `tests/e2e/conftest.py`
- Demo app running with User model boolean fields configured
- Checkbox form elements properly labeled for accessibility
- Database boolean field handling working correctly

## Related Files
- Main plan: `tests/e2e/plans/user_form_e2e_test_plan.md`
- Fixtures: `tests/e2e/conftest.py`
- Implementation: `tests/e2e/test_user_form_booleans.py` (to be created)
- User model: `demo_app/models.py` (for boolean field defaults)
- Related: Task 1 (basic functionality), Task 2 (validation patterns)

## Notes
- Checkbox default states may vary based on model configuration
- Some frameworks use hidden inputs alongside checkboxes for boolean fields
- Focus on user-visible checkbox state, not hidden form mechanics
- Test should work regardless of checkbox styling (custom vs native)
- Consider both mouse clicks and keyboard interaction for accessibility
- Boolean persistence is crucial for user experience in admin interfaces