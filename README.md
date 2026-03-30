<div align="center">
  <a href="https://yevheniidehtiar.github.io/hyper-admin/" target="_blank">
    <img src="https://yevheniidehtiar.github.io/hyper-admin/assets/logo.svg" alt="HyperAdmin Logo" width="150"/>
  </a>
  <h1>HyperAdmin</h1>
  <p>A modern, Pydantic-native admin interface for FastAPI, powered by HTMX.</p>

  <!-- Badges -->
  <p>
    <a href="https://github.com/yevheniidehtiar/hyper-admin/actions/workflows/ci.yml">
      <img src="https://github.com/yevheniidehtiar/hyper-admin/actions/workflows/ci.yml/badge.svg" alt="CI">
    </a>
    <a href="https://codecov.io/gh/yevheniidehtiar/hyper-admin">
      <img src="https://codecov.io/gh/yevheniidehtiar/hyper-admin/branch/main/graph/badge.svg" alt="Coverage">
    </a>
    <a href="https://pypi.org/project/hyperadmin/">
      <img src="https://img.shields.io/pypi/v/hyperadmin.svg" alt="PyPI">
    </a>
    <a href="https://pypi.org/project/hyperadmin/">
      <img src="https://img.shields.io/pypi/pyversions/hyperadmin.svg" alt="Python Versions">
    </a>
    <a href="https://github.com/astral-sh/ruff">
      <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff">
    </a>
    <a href="https://yevheniidehtiar.github.io/hyper-admin">
      <img src="https://img.shields.io/badge/docs-latest-blue.svg" alt="Docs">
    </a>
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
    </a>
  </p>

  > **Alpha** — HyperAdmin is under active development. APIs may change between releases.

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

```bash
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

## 🛠️ Development

```bash
# Install just (task runner)
# https://github.com/casey/just

# Bootstrap dev environment
just bootstrap

# Run linter + formatter
just lint

# Run tests
just test

# Serve docs locally
just docs
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgements

HyperAdmin stands on the shoulders of outstanding open-source projects and their communities:

- [**Django**](https://www.djangoproject.com/) — the original inspiration for what a batteries-included admin framework should feel like.
- [**FastAPI**](https://fastapi.tiangolo.com/) — the async Python web framework that makes building APIs a joy.
- [**Pydantic**](https://docs.pydantic.dev/) — the data validation backbone that powers HyperAdmin's model-first approach.
- [**HTMX**](https://htmx.org/) — for proving that modern, interactive UIs don't need mountains of JavaScript.
- [**SQLModel**](https://sqlmodel.tiangolo.com/) & [**SQLAlchemy**](https://www.sqlalchemy.org/) — the database layer that makes ORM integration seamless.
- [**Anthropic (Claude)**](https://www.anthropic.com/) — AI-assisted development that made it possible to build this project with a fraction of the usual time and effort.

Inspired by the conversations and ideas shared by [**Gergely Orosz**](https://www.pragmaticengineer.com/), [**ThePrimeagen**](https://www.youtube.com/@ThePrimeagen), [**Kent Beck**](https://www.kentbeck.com/), [**Steven Bartlett**](https://www.youtube.com/@TheDiaryOfACEO) and their guests.

Thank you to every maintainer, contributor, community member, and creator behind these projects and conversations.

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
