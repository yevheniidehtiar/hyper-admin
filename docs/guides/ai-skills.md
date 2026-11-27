# Claude Code Skills and Agents

The HyperAdmin repository ships [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
skills and agents for people building on HyperAdmin. A skill is a Markdown file with the steps,
API names and code for one kind of task; Claude Code loads it when a request matches its
description. An agent is a sub-assistant with its own instructions and tools.

They live in the repository's top-level
[`skills/`](https://github.com/yevheniidehtiar/hyper-admin/tree/develop/skills) and
[`agents/`](https://github.com/yevheniidehtiar/hyper-admin/tree/develop/agents) folders, and
describe the HyperAdmin version of the same commit.

## Skills

| Skill | Use it for |
|---|---|
| `hyperadmin-getting-started` | Installing HyperAdmin, mounting it on a FastAPI app, a first `ModelAdmin`, built-in or external auth, running it, a first test |
| `hyperadmin-define-ui` | Every declarative option: `ModelAdmin` attributes, `AdminOptions` (list, forms, fieldsets, inlines, relation widgets, detail panels, pagination), filters, actions, sidebar groups, reports and dashboard widgets |
| `hyperadmin-extend-ui` | Template and block overrides, widget templates, CSS tokens and theme presets, HTMX fragments, `data-testid` names, Playwright tests and screenshot baselines |
| `hyperadmin-new-plugin` | A plugin package: entry point, pages, sidebar entries, templates, static files, permissions, settings, lifecycle hooks, tests |
| `hyperadmin-migrate-from-django` | Porting a Django admin: mapping tables, converting models to SQLModel on the existing tables, auth, features with no equivalent yet, a parity checklist |
| `hyperadmin-migrate-from-flask` | Porting Flask-Admin with Flask-SQLAlchemy: mapping tables, moving models to a plain declarative base, access control, features with no equivalent yet, a parity checklist |

The migration skills follow [From Django Admin](../migration/from-django-admin.md) and
[From Flask-Admin](../migration/from-flask-admin.md), and add a step-by-step procedure.

## Agents

| Agent | What it does |
|---|---|
| `django-migration-agent` | Reads a Django project and reports its models and admin classes, how each option maps to HyperAdmin, and the gaps. When you approve the plan and name a target directory, it generates the HyperAdmin app one Django app at a time, with tests |
| `flask-migration-agent` | The same for a Flask-Admin project |

Until you approve, the agents only read the source project. They never change the source
project, its migrations or its database.

## Install

From a clone of the repository, pick one of these.

For every project on your machine, link them into your user folders:

```bash
mkdir -p ~/.claude/skills ~/.claude/agents
for skill in skills/hyperadmin-*; do ln -s "$PWD/$skill" ~/.claude/skills/; done
ln -s "$PWD"/agents/*-migration-agent.md ~/.claude/agents/
```

For one project, copy them into its `.claude/` folder:

```bash
mkdir -p your-project/.claude/skills your-project/.claude/agents
cp -R skills/hyperadmin-* your-project/.claude/skills/
cp agents/*-migration-agent.md your-project/.claude/agents/
```

As a Claude Code plugin, from inside Claude Code:

```text
/plugin marketplace add yevheniidehtiar/hyper-admin
/plugin install hyperadmin@hyperadmin
```

## Use

Ask for the task in your own words, for example "add a date filter and a bulk action to the
invoice admin" or "port the admin.py of this Django app". Claude Code picks the matching skill.
You can also call a skill by name, `/hyperadmin-define-ui`, and ask for an agent by name:
"use the django-migration-agent on ../legacy-site".

Refresh your copy when you upgrade HyperAdmin, so the skills match the installed version.
