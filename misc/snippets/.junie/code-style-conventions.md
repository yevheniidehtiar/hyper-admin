## Code Style Conventions
### Python Implementation Guidelines:
``` python
from sqlmodel import Session, SQLModel, Field, Relationship
from typing import Optional, List
import enum

class Status(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    email: str = Field(max_length=255, unique=True)
    is_active: bool = Field(default=True)
    status: Status = Field(default=Status.ACTIVE)

def create_user(session: Session, name: str, email: str, *, is_active: bool = True) -> User:
    user = User(name=name, email=email, is_active=is_active)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
```
### Error Handling Pattern:
``` python
from fastapi import HTTPException

def get_user_or_404(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, f"User {user_id} not found")
    return user
```
## HTMX Integration Conventions
### Essential Patterns:
``` html
<!-- Form with HTMX -->
<form hx-post="/admin/users" hx-target="#user-list" hx-swap="outerHTML">
    <input type="text" name="name" required>
    <button type="submit">Create User</button>
</form>

<!-- Dynamic loading -->
<div hx-get="/admin/users/search" 
     hx-trigger="keyup changed delay:500ms from:#search-input"></div>

<!-- Delete with confirmation -->
<button hx-delete="/admin/users/123" 
        hx-confirm="Delete?" 
        hx-target="closest tr">Delete</button>
```
### HTMX Response Handling:
``` python
@app.route("/admin/users", methods=["POST"])
async def create_user(request: Request):
    if "HX-Request" in request.headers:
        return templates.TemplateResponse("partials/user_row.html", {"request": request, "user": user})
    return RedirectResponse("/admin/users")
```
## Alpine.js Guidelines
### Component Structure:
``` html
<div x-data="userForm()" x-init="init()">
    <form @submit.prevent="submitForm">
        <input x-model="form.name" :class="{'border-red-500': errors.name}">
        <button :disabled="loading" x-text="loading ? 'Saving...' : 'Save'"></button>
    </form>
</div>

<script>
function userForm() {
    return {
        form: { name: '', email: '' },
        errors: {},
        loading: false,
        async submitForm() { /* implementation */ },
        validateField(field) { /* validation */ }
    }
}
</script>
```
## Tailwind CSS Guidelines
### Core Utility Patterns:
``` html
<!-- Form input -->
<input class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500">

<!-- Primary button -->
<button class="px-4 py-2 text-white bg-blue-600 rounded-md hover:bg-blue-700">Save</button>
```
### Component Class Definitions:
``` css
@layer components {
    .btn-primary { @apply px-4 py-2 text-white bg-blue-600 rounded-md hover:bg-blue-700; }
    .form-input { @apply w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500; }
}
