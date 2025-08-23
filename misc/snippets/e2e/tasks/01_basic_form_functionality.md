# Task 1: Basic Form Functionality Tests

## Overview
Implement basic smoke tests and minimal user creation functionality for the User form.

## Scope
- **Scenarios Covered**: 1-2 from main plan
- **Estimated Time**: 30-45 minutes
- **Prerequisites**: Basic Playwright knowledge, understanding of HTMX patterns

## Test Cases to Implement

### 1.1 Smoke Test: Open User Create Page
**File**: `test_user_form_basic.py::test_open_user_create_page`

**Steps**:
- Navigate to `/admin/user/create`
- Verify all expected form fields are present and visible

**Assertions**:
- Labels visible: "Username", "Email", "First Name", "Last Name", "Updated At", "Avatar", "Personal Key", "Is Active", "Is Superuser"
- "Save" button is visible and enabled
- Form element exists with proper structure

### 1.2 Create Minimal Valid User
**File**: `test_user_form_basic.py::test_create_minimal_valid_user`

**Steps**:
- Fill required text fields: Username, Email, First Name, Last Name
- Set boolean checkboxes: Is Active (checked), Is Superuser (unchecked)
- Click "Save" button
- Wait for redirect to user list

**Assertions**:
- HTMX submit occurs successfully (status 200/302)
- Redirect to `/admin/user` (list page)
- New user row appears in table with correct Username and Email
- No error messages displayed

## Implementation Guidelines

### Required Imports
```python
import pytest
from playwright.async_api import Page, expect
from pathlib import Path
```

### Test Structure
```python
@pytest.mark.asyncio
async def test_open_user_create_page(e2e_page: Page, demo_base_url: str):
    """Test that User create page loads with all expected fields."""
    # Implementation here

@pytest.mark.asyncio 
async def test_create_minimal_valid_user(e2e_page: Page, demo_base_url: str):
    """Test creating a user with minimal required fields."""
    # Implementation here
```

### Shared Test Data
```python
# Use these consistent values across tests
VALID_USER_DATA = {
    "username": "test_user_basic_001",
    "email": "basic_test+001@example.com", 
    "first_name": "Basic",
    "last_name": "Test"
}
```

### Key Selectors
- Form fields: `page.get_by_label("Field Name")`
- Save button: `page.get_by_role("button", name="Save")`
- User table: `page.locator("table")` or `page.get_by_role("table")`

## Success Criteria
- [ ] Both test cases pass consistently
- [ ] Tests use accessible selectors (get_by_label, get_by_role)  
- [ ] HTMX behavior verified (form submission + redirect)
- [ ] Tests are independent and can run in any order
- [ ] File size under 150 LOC
- [ ] No hardcoded waits (use Playwright's auto-waiting)

## Dependencies
- Fixtures: `e2e_page`, `demo_base_url` from `tests/e2e/conftest.py`
- Demo app must be running with User model accessible at `/admin/user`
- Database should be clean or tests should handle existing data gracefully

## Related Files
- Main plan: `tests/e2e/plans/user_form_e2e_test_plan.md`
- Fixtures: `tests/e2e/conftest.py`
- Implementation: `tests/e2e/test_user_form_basic.py` (to be created)

## Notes
- These are foundational tests - other task files will build upon this basic functionality
- Focus on happy path scenarios; validation testing is covered in Task 2
- Ensure consistent test data naming to avoid conflicts with other parallel tasks