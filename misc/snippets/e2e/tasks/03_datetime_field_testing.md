# Task 3: Datetime Field Tests

## Overview
Implement datetime field testing for the User form's "Updated At" field, covering optional empty values, valid datetime input, and invalid datetime validation.

## Scope
- **Scenarios Covered**: 6-8 from main plan
- **Estimated Time**: 30-45 minutes
- **Prerequisites**: Understanding of datetime input widgets, FastAPI datetime validation

## Test Cases to Implement

### 3.1 Datetime Optional Empty
**File**: `test_user_form_datetime.py::test_datetime_optional_empty`

**Steps**:
- Navigate to `/admin/user/create`
- Fill all required fields with valid values
- Leave "Updated At" field empty
- Click "Save" button
- Wait for successful redirect

**Assertions**:
- User creation succeeds (redirect to list page)
- New user appears in the user list
- Updated At field remains null/empty (not necessarily visible in list)
- No validation errors displayed

### 3.2 Datetime Valid Value
**File**: `test_user_form_datetime.py::test_datetime_valid_value`

**Steps**:
- Navigate to `/admin/user/create`
- Fill required fields with valid values
- Fill "Updated At" with valid datetime: "2025-08-17 19:25:00"
- Click "Save" button
- Wait for redirect, then navigate to edit page of created user

**Assertions**:
- User creation succeeds
- Navigate to edit page for the created user
- "Updated At" input field displays the entered value (or formatted equivalent)
- No validation errors during creation or editing

### 3.3 Datetime Invalid Value
**File**: `test_user_form_datetime.py::test_datetime_invalid_value`

**Steps**:
- Navigate to `/admin/user/create`
- Fill required fields with valid values
- Fill "Updated At" with invalid datetime: "abcdefg"
- Click "Save" button

**Assertions**:
- Server returns 422 status code
- Validation error alert block becomes visible
- Specific error message for datetime validation
- Form remains on create page
- Other valid field values are preserved

## Implementation Guidelines

### Required Imports
```python
import pytest
from playwright.async_api import Page, expect
from datetime import datetime
```

### Test Structure
```python
@pytest.mark.asyncio
async def test_datetime_optional_empty(e2e_page: Page, demo_base_url: str):
    """Test that Updated At field can be left empty."""
    # Implementation here

@pytest.mark.asyncio
async def test_datetime_valid_value(e2e_page: Page, demo_base_url: str):
    """Test valid datetime input and persistence."""
    # Implementation here

@pytest.mark.asyncio
async def test_datetime_invalid_value(e2e_page: Page, demo_base_url: str):
    """Test validation of invalid datetime input."""
    # Implementation here
```

### Test Data Constants
```python
# Datetime test values
DATETIME_TEST_DATA = {
    "valid_datetime": "2025-08-17 19:25:00",
    "invalid_datetime": "abcdefg",
    "alternative_valid": "2025-12-25 10:30:15"
}

# Base user data for datetime tests
DATETIME_USER_BASE = {
    "username": "test_user_datetime_001",
    "email": "datetime_test+001@example.com",
    "first_name": "Datetime",
    "last_name": "Test"
}
```

### Key Selectors
- Datetime field: `page.get_by_label("Updated At")`
- Form and error selectors same as validation tests
- Edit page URL pattern: `**/admin/user/edit/*`

### Helper Functions
```python
async def create_user_and_get_edit_url(page: Page, base_url: str, user_data: dict) -> str:
    """Create user and return edit page URL."""
    # Fill form, submit, extract user ID from redirect or table
    # Return constructed edit URL
    
async def fill_user_form(page: Page, user_data: dict, updated_at: str = None):
    """Helper to fill user form with optional datetime."""
    await page.get_by_label("Username").fill(user_data["username"])
    await page.get_by_label("Email").fill(user_data["email"])
    await page.get_by_label("First Name").fill(user_data["first_name"])
    await page.get_by_label("Last Name").fill(user_data["last_name"])
    
    if updated_at:
        await page.get_by_label("Updated At").fill(updated_at)
```

## Success Criteria
- [ ] All three datetime test cases pass consistently
- [ ] Optional empty datetime handling verified
- [ ] Valid datetime input and persistence tested
- [ ] Invalid datetime validation properly tested
- [ ] Tests handle both input widgets and plain text inputs
- [ ] File size under 150 LOC
- [ ] Tests are independent and use unique test data

## Dependencies
- Fixtures: `e2e_page`, `demo_base_url` from `tests/e2e/conftest.py`
- Demo app running with datetime field support
- FastAPI datetime validation configured
- User edit page accessible for persistence verification

## Related Files
- Main plan: `tests/e2e/plans/user_form_e2e_test_plan.md`
- Fixtures: `tests/e2e/conftest.py`
- Implementation: `tests/e2e/test_user_form_datetime.py` (to be created)
- Related: Task 1 (basic functionality), Task 2 (validation patterns)

## Notes
- Datetime widgets may vary (HTML5 datetime-local vs text input)
- Test should work with both widget types
- Focus on server-side datetime parsing and validation
- Consider timezone handling if relevant to the application
- Error messages may vary - focus on error state detection