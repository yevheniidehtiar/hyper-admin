<div align="center">
  <a href="https://yevheniidehtiar.github.io/hyper-admin/" target="_blank">
    <img src="https://yevheniidehtiar.github.io/hyper-admin/assets/logo.svg" alt="HyperAdmin Logo" width="150"/>
  </a>
  <h1>HyperAdmin</h1>
  <p>A modern, Pydantic-native admin interface for FastAPI, powered by HTMX.</p>

  <!-- Badges -->
  <p>
    <a href="https://github.com/yevheniidehtiar/hyper-admin/actions/workflows/ci.yml" target="_blank">
      <img alt="CI" src="https://github.com/yevheniidehtiar/hyper-admin/actions/workflows/ci.yml/badge.svg"/>
    </a>
    <a href="https://codecov.io/gh/yevheniidehtiar/hyper-admin" target="_blank">
      <img alt="Codecov" src="https://codecov.io/gh/yevheniidehtiar/hyper-admin/branch/main/graph/badge.svg"/>
    </a>
    <a href="https://pypi.org/project/hyperadmin/" target="_blank">
      <img alt="PyPI" src="https://img.shields.io/pypi/v/hyperadmin.svg"/>
    </a>
    <a href="https://pypi.org/project/hyperadmin/" target="_blank">
      <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/hyperadmin.svg"/>
    </a>
     <a href="https://github.com/yevheniidehtiar/hyper-admin/blob/main/LICENSE" target="_blank">
      <img alt="License" src="https://img.shields.io/pypi/l/hyperadmin"/>
    </a>
  </p>
</div>

---

**HyperAdmin** is a framework for building administrative interfaces on top of FastAPI applications. It leverages the power of **Pydantic** for data validation and **HTMX** for creating dynamic, modern user interfaces with minimal JavaScript. It is designed to be highly extensible and easy to use, allowing developers to quickly create rich, data-driven admin panels.

<div align="center">
  <!-- TODO: Add a screenshot or GIF of the admin interface -->
  <img src="https://placehold.co/800x400?text=HyperAdmin+Screenshot" alt="HyperAdmin Screenshot"/>
</div>

## ✨ Key Features

- **Pydantic-Native:** Define your admin interfaces directly from your Pydantic models.
- **FastAPI Integration:** Mounts seamlessly into any FastAPI application.
- **HTMX-Powered:** Delivers a rich, interactive user experience without writing complex JavaScript.
- **SQLModel & SQLAlchemy Support:** Works out-of-the-box with popular database libraries.
- **Automatic CRUD:** Generates list, detail, create, and update views from your data models.
- **Extensible:** Easily customize views, templates, and actions to fit your needs.

## 📚 Documentation

For a full guide on how to install, configure, and use HyperAdmin, please see the [**official documentation**](https://yevheniidehtiar.github.io/hyper-admin/).

## 🚀 Getting Started

### Installation

```sh
pip install hyperadmin
```

### Example Usage

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

Contributions are welcome! Please see the [Contributing Guide](https://yevheniidehtiar.github.io/hyper-admin/contributing/) for more details on how to get started.

<details>
<summary>Development Environment</summary>

This project uses `uv` for dependency management and `poe` for task automation.

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/yevheniidehtiar/hyper-admin.git
    cd hyper-admin
    ```

2.  **Create and sync the virtual environment:**
    ```sh
    uv sync --python 3.10 --all-extras
    ```

3.  **Activate the virtual environment:**
    ```sh
    source .venv/bin/activate
    ```

4.  **Install pre-commit hooks:**
    ```sh
    pre-commit install
    ```
Now you're ready to start developing! Run `poe` to see a list of available tasks.

</details>

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.