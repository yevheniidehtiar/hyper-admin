# HyperAdmin skills and agents for Claude Code

Skills and agents for people **building on** HyperAdmin: setting it up, declaring and extending
the UI, writing plugins, and moving an existing Django admin or Flask-Admin site over. They are
not needed to work on HyperAdmin itself.

| Skill | What it covers |
|---|---|
| [`hyperadmin-getting-started`](hyperadmin-getting-started/SKILL.md) | Install, mount on FastAPI, first `ModelAdmin`, built-in or external auth, run, a first test |
| [`hyperadmin-define-ui`](hyperadmin-define-ui/SKILL.md) | Every declarative option: `ModelAdmin` attributes, `AdminOptions`, filters, actions, detail panels, sidebar groups, reports and dashboards |
| [`hyperadmin-extend-ui`](hyperadmin-extend-ui/SKILL.md) | Template and block overrides, widget templates, CSS tokens, theme presets, HTMX fragments, `data-testid`s, Playwright tests, screenshot baselines |
| [`hyperadmin-new-plugin`](hyperadmin-new-plugin/SKILL.md) | A plugin package: entry point, pages, sidebar entries, templates, static files, permissions, settings, hooks, tests |
| [`hyperadmin-migrate-from-django`](hyperadmin-migrate-from-django/SKILL.md) | Django admin to HyperAdmin: mapping tables, model conversion to SQLModel, auth, gaps, parity checklist |
| [`hyperadmin-migrate-from-flask`](hyperadmin-migrate-from-flask/SKILL.md) | Flask-Admin and Flask-SQLAlchemy to HyperAdmin: mapping tables, models, access control, gaps, parity checklist |

| Agent | What it does |
|---|---|
| [`django-migration-agent`](../agents/django-migration-agent.md) | Reads a Django project, reports an inventory, a mapping and the gaps; after you approve the plan and name a target directory, generates the HyperAdmin app one Django app at a time, with tests |
| [`flask-migration-agent`](../agents/flask-migration-agent.md) | The same for a Flask-Admin project |

The agents read the target project only until you approve; they never change the source
project, its migrations or its database.

## Install

Pick one. The paths below are relative to a clone of the HyperAdmin repository.

**Copy or symlink into your user skills** (available in every project):

```bash
mkdir -p ~/.claude/skills ~/.claude/agents
for skill in skills/hyperadmin-*; do ln -s "$PWD/$skill" ~/.claude/skills/; done
ln -s "$PWD"/agents/*-migration-agent.md ~/.claude/agents/
```

**Copy into one project** (checked in with that project):

```bash
mkdir -p your-project/.claude/skills your-project/.claude/agents
cp -R skills/hyperadmin-* your-project/.claude/skills/
cp agents/*-migration-agent.md your-project/.claude/agents/
```

**Install as a plugin** (the repository is a plugin marketplace):

```text
/plugin marketplace add yevheniidehtiar/hyper-admin
/plugin install hyperadmin@hyperadmin
```

Plugin skills are namespaced, for example `hyperadmin:hyperadmin-define-ui`.

Claude Code picks a skill when your request matches its description ("add a filter to the
invoice list", "port my Django admin"). You can also name it: `/hyperadmin-define-ui`. Ask for
an agent by name: "use the django-migration-agent on ../legacy-site".

## Versions

The skills describe the HyperAdmin version in the same commit. Use the copy that matches the
version you install (`pip install hyper-admin==<version>`), and refresh it when you upgrade.
`tests/unit/test_user_skills.py` checks that their frontmatter is valid, that complete code
blocks parse, and that every `hyperadmin` import they name resolves.
