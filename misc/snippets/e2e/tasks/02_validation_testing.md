# Task 2: Form Validation Tests

## Overview
Implement comprehensive validation testing for the User form, covering required fields, format validation, and length constraints.

## Scope
- **Scenarios Covered**: 3-5 from main plan
- **Estimated Time**: 45-60 minutes
- **Prerequisites**: Basic Playwright knowledge, understanding of FastAPI validation responses

## Test Cases to Implement

### 2.1 Required Fields Validation
**File**: `test_user_form_validation.py::test_required_fields_validation`

**Steps**:
- Navigate to `/admin/user/create`
- Leave Username and Email fields empty
- Fill optional fields (First Name, Last Name) with valid values
- Click "Save" button

**Assertions**:
- Server returns 422 status code
- Validation error alert block becomes visible
- Error messages displayed for Username and Email fields
- Form remains on create page (no redirect)
- Other field values are preserved

### 2.2 Email Format Validation
**File**: `test_user_form_validation.py::test_email_format_validation`

**Steps**:
- Fill Email with invalid format: "not-an-email"
- Fill other required fields with valid values
- Click "Save" button

**Assertions**:
- Server returns 422 status code
- Validation error alert block visible
- Specific error message for email format validation
- Form values preserved except for the invalid email

### 2.3 Max Length Validation
**File**: `test_user_form_validation.py::test_max_length_validation`

**Steps**:
- Fill Username with string > 50 characters
- Fill First Name or Last Name with string > 50 characters  
- Fill other required fields with valid values
- Click "Save" button

**Assertions**:
- Server returns 422 status code
- Validation error alert block visible
- Error messages for fields exceeding max length
- Valid field values are preserved

## Implementation Guidelines

### Required Imports
```python
import pytest
from playwright.async_api import Page, expect
```

### Test Structure
```python
@pytest.mark.asyncio
async def test_required_fields_validation(e2e_page: Page, demo_base_url: str):
    """Test validation when required fields are empty."""
    # Implementation here

@pytest.mark.asyncio
async def test_email_format_validation(e2e_page: Page, demo_base_url: str):
    """Test email format validation."""
    # Implementation here

@pytest.mark.asyncio
async def test_max_length_validation(e2e_page: Page, demo_base_url: str):
    """Test field length validation."""
    # Implementation here
```

### Test Data Constants
```python
# Invalid test data
INVALID_TEST_DATA = {
    "invalid_email": "not-an-email",
    "long_username": "a" * 51,  # 51 chars, exceeds 50 limit
    "long_first_name": "b" * 51,
    "long_last_name": "c" * 51
}

# Valid baseline data for mixed validation tests
VALID_BASELINE = {
    "username": "test_user_validation_001",
    "email": "validation_test+001@example.com",
    "first_name": "Valid",
    "last_name": "User"
}
```

### Key Selectors
- Error alert block: `page.locator(".alert-danger")` or `page.get_by_role("alert")`
- Form fields: `page.get_by_label("Field Name")`
- Error messages: `page.locator(".invalid-feedback")` or within alert block

### Validation Response Patterns
```python
# Helper function to check validation errors
async def assert_validation_error_displayed(page: Page):
    """Assert that validation error UI is displayed."""
    error_block = page.locator(".alert-danger, [role='alert']")
    await expect(error_block).to_be_visible()
    await expect(page).to_have_url("**/admin/user/create")  # Still on create page
```

## Success Criteria
- [ ] All three validation test cases pass consistently
- [ ] Tests properly verify 422 status codes from server
- [ ] Error messages are properly displayed in UI
- [ ] Form state is preserved on validation errors
- [ ] Tests use accessible selectors for error detection
- [ ] File size under 150 LOC
- [ ] No hardcoded waits or sleeps

## Dependencies
- Fixtures: `e2e_page`, `demo_base_url` from `tests/e2e/conftest.py`
- Demo app must be running with proper validation configured
- FastAPI validation should return 422 for validation errors
- Error display templates must be properly implemented

## Related Files
- Main plan: `tests/e2e/plans/user_form_e2e_test_plan.md`
- Fixtures: `tests/e2e/conftest.py`
- Implementation: `tests/e2e/test_user_form_validation.py` (to be created)
- Related: Task 1 for basic form functionality

## Notes
- Focus on server-side validation responses, not client-side validation
- Ensure test data doesn't conflict with other parallel tasks
- Consider testing multiple validation errors simultaneously
- Error message text may vary - focus on error state rather than exact wording