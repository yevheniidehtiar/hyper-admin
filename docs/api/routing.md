# Routing

## URL structure

For each registered model (e.g. `Product`), the following routes are generated under your mount prefix (e.g. `/admin`):

| Method | Pattern | View | Controlled by |
|--------|---------|------|---------------|
| `GET` | `/admin/product/` | List view | `can_list` |
| `GET` | `/admin/product/create` | Create form | `can_create` |
| `POST` | `/admin/product/` | Handle create | `can_create` |
| `GET` | `/admin/product/{id}` | Detail view | `can_detail` |
| `GET` | `/admin/product/{id}/edit` | Edit form | `can_edit` |
| `PUT` | `/admin/product/{id}` | Handle update | `can_edit` |
| `DELETE` | `/admin/product/{id}` | Delete action | `can_delete` |

Routes are only registered for operations enabled by `AdminOptions`.

## HyperAdminRouter

::: hyperadmin.routing.HyperAdminRouter