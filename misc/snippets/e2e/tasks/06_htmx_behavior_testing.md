# Task 6: HTMX Behavior Tests

## Overview
Implement HTMX-specific behavior testing for the User form, covering form submission mechanics, redirect handling, and partial response validation.

## Scope
- **Scenarios Covered**: 13-15 from main plan
- **Estimated Time**: 45-60 minutes
- **Prerequisites**: Understanding of HTMX patterns, network request interception, response header handling

## Test Cases to Implement

### 6.1 HTMX Form Submission and Redirects
**File**: `test_user_form_htmx.py::test_htmx_form_submission_and_redirects`

**Steps**:
- Navigate to `/admin/user/create`
- Fill form with valid data
- Capture network response during form POST submission
- Click "Save" button
- Verify redirect behavior

**Assertions**:
- Form POST request contains `HX-Request: true` header
- Server response includes appropriate redirect mechanism:
  - Either `HX-Redirect` header with redirect URL, OR
  - Direct navigation occurs to `/admin/user` list page
- Form submission uses HTMX (not traditional form post)
- No full page reload during submission

### 6.2 HTMX Partial Response Validation
**File**: `test_user_form_htmx.py::test_htmx_partial_response_validation`

**Steps**:
- Navigate to `/admin/user/create`
- Fill form with valid data
- Intercept and inspect the form POST response body
- Submit form and capture response

**Assertions**:
- Response body is partial HTML (does not contain `<html>` tag)
- Response contains appropriate content for HTMX handling
- Content-Type header is `text/html` or similar
- Response structure supports HTMX swapping/targeting

### 6.3 Save and Continue Behavior
**File**: `test_user_form_htmx.py::test_save_and_continue_behavior`

**Steps**:
- Navigate to `/admin/user/create`
- Fill form with valid data
- Click "Save and Continue" button (if available)
- Verify redirect to edit page

**Assertions**:
- User is created successfully
- Redirect occurs to edit page of the new object
- URL contains `/admin/user/edit/{id}` pattern
- `HX-Object-ID` header or similar mechanism used for redirect
- Edit form loads with saved data

### 6.4 Save and Add Another Behavior  
**File**: `test_user_form_htmx.py::test_save_and_add_another_behavior`

**Steps**:
- Navigate to `/admin/user/create`
- Fill form with valid data
- Click "Save and Add Another" button (if available)
- Verify redirect back to create page

**Assertions**:
- User is created successfully
- Redirect occurs back to `/admin/user/create`
- Form is reset (empty fields)
- Ready for creating another user
- Success message displayed (optional)

## Implementation Guidelines

### Required Imports
```python
import pytest
from playwright.async_api import Page, expect, Request, Response
import json
```

### Test Structure
```python
@pytest.mark.asyncio
async def test_htmx_form_submission_and_redirects(e2e_page: Page, demo_base_url: str):
    """Test HTMX form submission mechanics and redirect handling."""
    # Implementation here

@pytest.mark.asyncio
async def test_htmx_partial_response_validation(e2e_page: Page, demo_base_url: str):
    """Test that HTMX responses are partial HTML."""
    # Implementation here

@pytest.mark.asyncio
async def test_save_and_continue_behavior(e2e_page: Page, demo_base_url: str):
    """Test Save and Continue redirect to edit page."""
    # Implementation here

@pytest.mark.asyncio
async def test_save_and_add_another_behavior(e2e_page: Page, demo_base_url: str):
    """Test Save and Add Another redirect to create page."""
    # Implementation here
```

### Test Data Constants
```python
# Base user data for HTMX tests
HTMX_USER_BASE = {
    "username": "test_user_htmx_001",
    "email": "htmx_test+001@example.com",
    "first_name": "HTMX",
    "last_name": "Test"
}
```

### Network Interception Patterns
```python
# Capture form POST requests
async def capture_form_post_request(page: Page, base_url: str) -> tuple[Request, Response]:
    """Capture the form POST request and response."""
    request_data = None
    response_data = None
    
    # Set up request/response listeners
    def handle_request(request: Request):
        nonlocal request_data
        if request.method == "POST" and "/admin/user" in request.url:
            request_data = request
    
    def handle_response(response: Response):
        nonlocal response_data
        if response.request.method == "POST" and "/admin/user" in response.url:
            response_data = response
    
    page.on("request", handle_request)
    page.on("response", handle_response)
    
    return request_data, response_data

# HTMX header validation
async def assert_htmx_request_headers(request: Request):
    """Assert that request contains HTMX headers."""
    headers = request.headers
    assert "hx-request" in headers or "HX-Request" in headers
    # Additional HTMX header checks as needed

async def assert_htmx_response_format(response: Response):
    """Assert that response is in HTMX-compatible format."""
    body = await response.text()
    headers = response.headers
    
    # Should be partial HTML, not full page
    assert "<html" not in body.lower(), "Response should be partial HTML"
    assert "text/html" in headers.get("content-type", "")
```

### Button Detection and Interaction
```python
async def click_save_button_variant(page: Page, button_type: str = "save"):
    """Click different variants of save buttons."""
    button_selectors = {
        "save": 'button[type="submit"], page.get_by_role("button", name="Save")',
        "save_continue": 'page.get_by_role("button", name="Save and Continue")',
        "save_add_another": 'page.get_by_role("button", name="Save and Add Another")'
    }
    
    if button_type == "save_continue":
        try:
            await page.get_by_role("button", name="Save and Continue").click()
        except:
            # Fallback if button doesn't exist
            await page.get_by_role("button", name="Save").click()
    elif button_type == "save_add_another":
        try:
            await page.get_by_role("button", name="Save and Add Another").click()
        except:
            # Fallback if button doesn't exist
            await page.get_by_role("button", name="Save").click()
    else:
        await page.get_by_role("button", name="Save").click()
```

### Helper Functions
```python
async def fill_user_form_for_htmx_test(page: Page, user_data: dict):
    """Fill user form for HTMX behavior testing."""
    await page.get_by_label("Username").fill(user_data["username"])
    await page.get_by_label("Email").fill(user_data["email"])
    await page.get_by_label("First Name").fill(user_data["first_name"])
    await page.get_by_label("Last Name").fill(user_data["last_name"])

async def extract_user_id_from_url(url: str) -> str:
    """Extract user ID from edit page URL."""
    # Parse URL like /admin/user/edit/123 to get ID
    parts = url.split("/")
    return parts[-1] if parts[-1].isdigit() else None
```

## Success Criteria
- [ ] HTMX form submission mechanics verified
- [ ] Partial response validation passes
- [ ] Save and Continue behavior tested (if implemented)
- [ ] Save and Add Another behavior tested (if implemented)
- [ ] Network request/response interception works reliably
- [ ] HTMX-specific headers properly validated
- [ ] Tests gracefully handle missing optional buttons
- [ ] File size under 150 LOC per test case

## Dependencies
- Fixtures: `e2e_page`, `demo_base_url` from `tests/e2e/conftest.py`
- Demo app with HTMX properly configured
- Form submission endpoints returning appropriate HTMX responses
- Save button variants implemented (or graceful fallback handling)

## Related Files
- Main plan: `tests/e2e/plans/user_form_e2e_test_plan.md`
- Fixtures: `tests/e2e/conftest.py` 
- Implementation: `tests/e2e/test_user_form_htmx.py` (to be created)
- HTMX configuration: Check FastAPI routes and templates
- Related: Task 1 (basic functionality for comparison)

## Notes
- Some save button variants may not be implemented yet - tests should handle gracefully
- HTMX response format may vary based on implementation approach
- Focus on HTMX mechanics rather than visual presentation
- Network timing may require careful handling in tests
- Consider both successful submissions and error cases for HTMX behavior
- Response inspection should be robust to different HTMX implementation patterns