# Task 4: File Upload Tests

## Overview
Implement file upload testing for the User form's Avatar (image) and Personal Key (generic file) fields, covering valid uploads, invalid file types, and upload persistence.

## Scope
- **Scenarios Covered**: 9-11 from main plan
- **Estimated Time**: 45-60 minutes
- **Prerequisites**: Understanding of file upload widgets, multipart form handling, file validation

## Test Cases to Implement

### 4.1 Avatar Image Upload (Valid)
**File**: `test_user_form_uploads.py::test_avatar_image_upload_valid`

**Steps**:
- Navigate to `/admin/user/create`
- Fill all required fields with valid values
- Attach a small valid PNG/JPG file to "Avatar" field
- Click "Save" button
- Navigate to edit page of created user

**Assertions**:
- User creation succeeds (redirect to list page)
- No server errors during upload processing
- Edit page loads successfully (avatar field ready but cannot read path)
- Uploaded file exists in expected location (optional verification)

### 4.2 Avatar Invalid File Type
**File**: `test_user_form_uploads.py::test_avatar_invalid_file_type`

**Steps**:
- Navigate to `/admin/user/create`
- Fill all required fields with valid values
- Attach a .txt file to "Avatar" field (expecting image)
- Click "Save" button

**Assertions**:
- Server returns 422 status code OR sanitizes/rejects the file
- If validation error: error alert block visible with file type message
- If sanitized: creation succeeds but avatar field remains empty
- Other valid field values are preserved

### 4.3 Personal Key Generic File Upload
**File**: `test_user_form_uploads.py::test_personal_key_file_upload`

**Steps**:
- Navigate to `/admin/user/create`
- Fill all required fields with valid values
- Attach a small .txt or .pem file to "Personal Key" field
- Click "Save" button

**Assertions**:
- User creation succeeds (redirect to list page)
- No validation errors displayed
- No server errors during upload processing
- File upload handled correctly by the server

## Implementation Guidelines

### Required Imports
```python
import pytest
from playwright.async_api import Page, expect
from pathlib import Path
import tempfile
import os
```

### Test Structure
```python
@pytest.mark.asyncio
async def test_avatar_image_upload_valid(e2e_page: Page, demo_base_url: str):
    """Test valid image upload for avatar field."""
    # Implementation here

@pytest.mark.asyncio
async def test_avatar_invalid_file_type(e2e_page: Page, demo_base_url: str):
    """Test invalid file type validation for avatar."""
    # Implementation here

@pytest.mark.asyncio
async def test_personal_key_file_upload(e2e_page: Page, demo_base_url: str):
    """Test generic file upload for personal key field."""
    # Implementation here
```

### Test Data and File Creation
```python
# Base user data for upload tests
UPLOAD_USER_BASE = {
    "username": "test_user_upload_001",
    "email": "upload_test+001@example.com",
    "first_name": "Upload",
    "last_name": "Test"
}

def create_test_image(size_kb: int = 10) -> Path:
    """Create a small test PNG image."""
    # Create minimal PNG file for testing
    # Return path to temporary file
    
def create_test_text_file(content: str = "test content") -> Path:
    """Create a small test text file."""
    # Create temporary text file
    # Return path to temporary file
    
def create_test_pem_file() -> Path:
    """Create a small test PEM file."""
    # Create temporary PEM-like file
    # Return path to temporary file
```

### File Fixture Setup
```python
@pytest.fixture
async def test_avatar_image():
    """Create temporary test image file."""
    temp_file = create_test_image(size_kb=5)  # Small PNG
    yield temp_file
    # Cleanup
    if temp_file.exists():
        temp_file.unlink()

@pytest.fixture  
async def test_text_file():
    """Create temporary text file."""
    temp_file = create_test_text_file("test personal key content")
    yield temp_file
    # Cleanup
    if temp_file.exists():
        temp_file.unlink()

@pytest.fixture
async def invalid_avatar_file():
    """Create text file for invalid avatar test."""
    temp_file = create_test_text_file("not an image")
    yield temp_file
    # Cleanup
    if temp_file.exists():
        temp_file.unlink()
```

### Key Selectors and Upload Pattern
```python
# File upload pattern
async def upload_file_to_field(page: Page, field_label: str, file_path: Path):
    """Upload file to specified field."""
    await page.get_by_label(field_label).set_input_files(str(file_path))

# Key selectors
# - Avatar field: page.get_by_label("Avatar")  
# - Personal Key field: page.get_by_label("Personal Key")
# - File input elements: input[type="file"]
```

### Helper Functions
```python
async def fill_user_form_with_uploads(
    page: Page, 
    user_data: dict, 
    avatar_file: Path = None, 
    personal_key_file: Path = None
):
    """Fill user form including file uploads."""
    # Fill text fields
    await page.get_by_label("Username").fill(user_data["username"])
    await page.get_by_label("Email").fill(user_data["email"])
    await page.get_by_label("First Name").fill(user_data["first_name"])
    await page.get_by_label("Last Name").fill(user_data["last_name"])
    
    # Upload files if provided
    if avatar_file:
        await upload_file_to_field(page, "Avatar", avatar_file)
    if personal_key_file:
        await upload_file_to_field(page, "Personal Key", personal_key_file)
```

## Success Criteria
- [ ] Valid image upload test passes consistently
- [ ] Invalid file type handling verified (validation or sanitization)
- [ ] Generic file upload test passes
- [ ] File upload doesn't break form submission
- [ ] Tests properly clean up temporary files
- [ ] File size limits respected (< 50KB test files)
- [ ] Tests are independent and use unique test data

## Dependencies
- Fixtures: `e2e_page`, `demo_base_url` from `tests/e2e/conftest.py`
- Demo app with file upload support configured
- File upload directory permissions properly set
- Multipart form handling in FastAPI backend
- File validation configured (if any)

## Related Files
- Main plan: `tests/e2e/plans/user_form_e2e_test_plan.md`
- Fixtures: `tests/e2e/conftest.py`
- Implementation: `tests/e2e/test_user_form_uploads.py` (to be created)
- Upload directory: `demo_app/uploads/` (or configured upload path)
- Related: Task 1 (basic functionality), Task 2 (validation patterns)

## Notes
- Test files should be small (< 50KB) to avoid slow tests
- Consider both file validation and sanitization approaches
- File cleanup is important to avoid test pollution
- Upload directory must exist and be writable
- Avatar field may have specific image type restrictions
- Personal Key field should accept various file types
- Focus on upload mechanics, not file content validation