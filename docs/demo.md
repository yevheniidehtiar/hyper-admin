# Live Demo

HyperAdmin ships with a runnable **ERP (bookkeeping) demo** — a small FastAPI
application that wires up several sub-apps (contacts, sales, purchases,
accounting, reports) behind the HyperAdmin admin interface. It is the fastest
way to see HyperAdmin in action.

The source lives in [`examples/erp/`](https://github.com/yevheniidehtiar/hyper-admin/tree/develop/examples/erp).

## Hosted demo

A hosted instance is deployed to [Fly.io](https://fly.io) as the
`hyperadmin-demo` app. Once a maintainer has configured the deployment secrets
(see below), the admin UI is available at:

```
https://hyperadmin-demo.fly.dev/admin
```

!!! note "Deployment is opt-in"
    The deployment pipeline (`.github/workflows/demo-deploy.yml`) is **inert
    until secrets are configured**. If the `FLY_API_TOKEN` secret is not set,
    the deploy step logs a warning and no-ops cleanly, so the workflow never
    fails on forks or unconfigured repositories.

## Run it locally

The demo is fully self-contained and seeds its own SQLite database on startup.

### With Docker Compose (recommended)

```bash
cd examples/erp
docker compose up --build
```

Then open <http://localhost:8000/admin>.

### Without Docker

From the repository root:

```bash
uv sync --all-extras
uv run fastapi dev examples/erp/main.py
```

The app listens on port **8000** and the admin interface is mounted at
`/admin`. The root path (`/`) returns a small pointer to the admin UI.

## Deploying the hosted demo (maintainers)

Deployment runs via the `Deploy Demo` GitHub Actions workflow, triggered by:

- **Manual dispatch** — run it from the **Actions** tab (`workflow_dispatch`).
- **A `demo-*` tag** — for example:

  ```bash
  git tag demo-2026-06-02
  git push origin demo-2026-06-02
  ```

The workflow always builds the image from `examples/erp/Dockerfile` (so a
broken Dockerfile fails the run regardless of secrets), then deploys to Fly.io
only when `FLY_API_TOKEN` is present.

### Required GitHub secrets

To enable the live deployment, a maintainer must set the following repository
secrets (**Settings → Secrets and variables → Actions**):

| Secret | Purpose | How to obtain |
|---|---|---|
| `FLY_API_TOKEN` | Authenticates `flyctl` for deploys. Without it the deploy step no-ops. | `fly tokens create deploy` (scoped to the `hyperadmin-demo` app) |
| `HYPERADMIN_SECRET_KEY` | Session signing key for the demo app. Optional but recommended; pushed to Fly as an app secret. | Any high-entropy string, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |

The Fly app itself is defined in [`examples/erp/fly.toml`](https://github.com/yevheniidehtiar/hyper-admin/tree/develop/examples/erp/fly.toml)
(app name `hyperadmin-demo`, internal port `8000`).
