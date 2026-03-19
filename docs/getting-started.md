# Getting Started

This page will guide you through setting up HyperAdmin.

## Template Overriding

HyperAdmin allows you to override the default templates for the admin interface. This is useful when you want to customize the look and feel of your admin panel.

### Providing Custom Template Directories

You can provide a list of custom template directories to the `Admin` instance using the `template_dirs` argument:

```python
from fastapi import FastAPI
from hyperadmin import Admin

app = FastAPI()
admin = Admin(app, template_dirs=["my_templates/"])
```

### Template Naming Convention

HyperAdmin uses a specific naming convention to resolve templates. The templates are searched in the following order:

1.  `{app_label}/{model_name}/{view_name}.html`
2.  `{app_label}/{model_name}/default.html`
3.  `{app_label}/{view_name}.html`
4.  `{app_label}/default.html`
5.  `{view_name}.html`
6.  `default.html`

-   `app_label`: The name of the application module where the model is defined.
-   `model_name`: The lowercase name of the model class.
-   `view_name`: The name of the view, e.g., `list`, `detail`, `create`, `update`.

For example, to override the list view for a `User` model in a `users` app, you would create a file named `my_templates/users/user/list.html`.
