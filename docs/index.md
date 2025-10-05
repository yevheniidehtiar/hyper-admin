<div align="center">
  <a href="https://yevheniidehtiar.github.io/hyper-admin/" target="_blank">
    <img src="assets/logo.svg" alt="HyperAdmin Logo" width="150"/>
  </a>
  <h1>HyperAdmin</h1>
  <p>A modern, Pydantic-native admin interface for FastAPI, powered by HTMX.</p>
</div>

---

**HyperAdmin** is a framework for building administrative interfaces on top of FastAPI applications. It leverages the power of **Pydantic** for data validation and **HTMX** for creating dynamic, modern user interfaces with minimal JavaScript. It is designed to be highly extensible and easy to use, allowing developers to quickly create rich, data-driven admin panels.

## ✨ Key Features

- **Pydantic-Native:** Define your admin interfaces directly from your Pydantic models.
- **FastAPI Integration:** Mounts seamlessly into any FastAPI application.
- **HTMX-Powered:** Delivers a rich, interactive user experience without writing complex JavaScript.
- **SQLModel & SQLAlchemy Support:** Works out-of-the-box with popular database libraries.
- **Automatic CRUD:** Generates list, detail, create, and update views from your data models.
- **Extensible:** Easily customize views, templates, and actions to fit your needs.

## 📚 Navigation

- **[Getting Started](getting-started.md):** A guide to installing and configuring HyperAdmin.
- **[Tutorial](tutorial.md):** A step-by-step tutorial on how to use HyperAdmin.
- **[API Reference](api/):** Detailed documentation of the HyperAdmin API.

## 🚀 Example Usage

```python
from fastapi import FastAPI
from hyperadmin.admin import Admin
from hyperadmin.views import ModelView
from sqlmodel import SQLModel, Field

# 1. Define your data model
class Product(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    price: float

# 2. Create a FastAPI app
app = FastAPI()

# 3. Create an admin instance and register your model
admin = Admin()
admin.register_model(ModelView(Product))

# 4. Mount the admin to your app
admin.mount_to(app)
```
This will automatically create a full CRUD interface for your `Product` model at `/admin`.

## 🤝 Contributing

Contributions are welcome! Please see the [Contributing Guide](https://github.com/yevheniidehtiar/hyper-admin/blob/main/CONTRIBUTING.md) for more details on how to get started.