# How HyperAdmin is verified

This page lists the checks that guard each release and links each one to the code that runs it.
Figures that change often (test counts, load-test results) carry the date they were taken, or
link to the page that keeps them current.

Links to files point at the `develop` branch on GitHub.

## Test suites

Counted on 2026-11-27 at commit `60922279` with `uv run pytest <path> --collect-only -q`:

| Suite | Path | Tests collected |
|---|---|---:|
| Unit and integration | [`tests/unit/`][repo-unit] (247 test files) | 4,001 |
| `hyperadmin-reports` plugin | [`plugins/hyperadmin-reports/tests/`][repo-reports] | 338 |
| `hyperadmin-tasks` plugin | [`plugins/hyperadmin-tasks/tests/`][repo-tasks] | 382 |
| `hyperadmin-logfire` plugin | [`plugins/hyperadmin-logfire/tests/`][repo-logfire] | 48 |
| End-to-end (Playwright, Chromium) | [`tests/e2e/`][repo-e2e] (64 test files) | 425 |

The unit suites run against in-memory SQLite and the ASGI app in-process. The E2E suite starts
real servers on free ports, from the apps in [`tests/e2e/apps/`][repo-e2e-apps] and the
examples, and drives them in a browser. E2E tests are written from Given/When/Then scenarios and
carry them as comments.

To reproduce the counts:

```bash
uv sync --all-extras
uv run pytest tests/unit --collect-only -q | tail -1
uv run pytest tests/e2e --collect-only -q | tail -1
```

## Continuous integration

Two workflows run on every pull request to `develop` and on every push to `develop` and
`master`. A pull request that changes only documentation skips the code jobs.

| Workflow | Pull request | Push to `develop` / `master` |
|---|---|---|
| [`ci.yml`][repo-ci] | Ruff, `ruff format --check`, mypy, basedpyright on Python 3.11. Unit and plugin tests on Python 3.11 and 3.14, on Ubuntu and macOS | The same lint job. Unit tests on Python 3.11 to 3.15 on Ubuntu, and 3.11, 3.14, 3.15 on macOS |
| [`test.yml`][repo-test] | `poe lint` (all pre-commit hooks) on 3.11. Unit tests on Python 3.14 with the locked (highest) versions and on Python 3.11 with the lowest versions the dependency bounds allow (`--resolution lowest-direct`). E2E suite on 3.14 in 3 shards | Unit tests on every Python 3.11 to 3.14, each with highest and lowest-direct resolution (8 rows). E2E suite in 3 shards |

The lowest-direct rows check the lower bounds in `[project.dependencies]` of
[`pyproject.toml`][repo-pyproject]: they install the oldest release each bound allows and run the
whole unit suite against it. The supported versions are listed in
[Compatibility & Performance](compatibility.md#supported-stacks).

Locally, `poe deps:bump` runs `poe lint` and the unit suite on four combinations (Python 3.11 and
3.14 with lowest-direct, 3.14 and 3.15 with highest) before a dependency bump is committed; see
the `deps:bump` task in [`pyproject.toml`][repo-pyproject]. The pre-push hook in
[`.pre-commit-config.yaml`][repo-precommit] runs the unit suite on Python 3.14 and the security
checks.

### Databases

CI runs on SQLite (`aiosqlite`). PostgreSQL is covered by the load tests below, by unit tests
that compile queries for the PostgreSQL dialect (for example
[`tests/unit/adapters/test_search_like.py`][repo-search-like]), and by the runs on real
applications in [Compatibility & Performance](compatibility.md#tested-on-real-open-source-apps).
MySQL is not verified yet.

## Coverage of changed lines

Every changed line must be covered by a test.

- CI uploads the coverage of the unit run in [`ci.yml`][repo-ci] to Codecov.
  [`codecov.yml`][repo-codecov] sets the patch target to 100% with no threshold, and the
  project target to "never drop".
- `poe test:cov-diff` runs the same check locally: the unit and plugin suites, then
  `diff-cover --compare-branch=origin/develop --fail-under=100`
  (see [`pyproject.toml`][repo-pyproject]).

## Visual regression

[`tests/e2e/test_visual_regression.py`][repo-visual] takes full-page screenshots and compares
them with committed baselines in [`tests/e2e/snapshots/`][repo-snapshots]. A test fails when more
than 1% of the pixels differ by more than 30/255 in any channel. That tolerance absorbs font
antialiasing and leaves layout changes (a sidebar that reappears on a phone, a table that loses
its card layout) above the limit. Timestamp cells are pinned to one value before the capture, so
the baselines pin layout, not data.

17 baselines are committed per platform: one set for Linux (what CI compares against) and one in
`darwin/` for local runs on macOS.

| Page | Widths | Test |
|---|---|---|
| List, create form, detail, login | 375, 768, 1024 px | [`test_visual_regression.py`][repo-visual] |
| Permissions matrix | 375, 768, 1024 px | [`test_permissions_matrix.py`][repo-perm-matrix] |
| Report chart | 1024 px | [`test_chart_visual.py`][repo-charts] |
| List in English (left-to-right) | 1280 px | [`test_i18n.py`][repo-e2e-i18n] |

The baselines render the default `terminal` theme preset in light mode. After an intentional
visual change, they are regenerated with `RESPONSIVE_SNAPSHOTS_UPDATE=1` (the module docstring
of `test_visual_regression.py` has the commands for both platforms). When a CI comparison fails,
the job uploads the actual and diff images as an artifact.

## Public API snapshot

[`tests/unit/test_public_api.py`][repo-public-api] builds the public API defined in the
[versioning policy](versioning.md#what-is-public-api) from the code and from these docs: every
name in `hyperadmin.__all__`, every `hyperadmin` name a page imports or references, the members
of those classes, the `HYPERADMIN_*` settings, the plugin contract and the `hyperadmin` CLI.
It renders one line per entry and compares the result with
[`public_api_snapshot.txt`][repo-public-api-snapshot]. Any change to a signature, a default or
an export fails the test with a diff, so an API change is always a reviewed edit of that file.

[`tests/unit/test_settings_documented.py`][repo-settings-doc] fails when a
`HyperAdminSettings` field has no row in a settings table of these docs.

## Translations

The admin ships 20 locale catalogs in [`src/hyperadmin/locale/`][repo-locale]. The unit suite
checks them:

- [`test_i18n_catalogs.py`][repo-i18n-catalogs]: a compiled `.mo` file exists and loads for
  every locale, every non-English catalog declares a `Plural-Forms` header, and fuzzy entries
  fall back to the English text.
- [`test_i18n_v059_catalogs.py`][repo-i18n-v059]: every catalog carries the navigation and
  keyboard strings, and sidebar group labels are extracted and translated.
- [`test_i18n_rtl.py`][repo-i18n-rtl]: right-to-left locales render with `dir="rtl"`.
- [`test_validation_messages_i18n.py`][repo-i18n-validation]: Pydantic validation messages are
  translated by error type, and unknown types fall back to the Pydantic wording.

## Load tests

[`loadtest.yml`][repo-loadtest-ci] runs the ERP example under Locust:

- on pull requests that touch the adapters, views or core: SQLite, 10 users for 30 seconds;
- nightly: PostgreSQL with 100,000 seeded rows, 100 users for 5 minutes.

Both runs fail when an endpoint's error rate goes over the limit in
[`examples/erp/loadtest/baselines.py`][repo-baselines], which also compares p95 latency with a
recorded baseline when one is committed.

The measured results, the database comparison at 1.2 million rows
([`scripts/loadtest_scale.py`][repo-loadtest-scale]) and how to run the same tests on your own
deployment are in [Compatibility & Performance](compatibility.md#under-load). The database
comparison runs only on an idle host and measures everything twice.

## Demo tour and screenshots

The screenshots and the video in these docs are generated from seeded apps in this repository,
not drawn by hand:

- [`scripts/demo_tour_video.py`][repo-tour] starts the ERP example and the E2E test apps, each
  on a free port with a throwaway database, plays each scene in Chromium, and writes the video,
  the poster and the screenshots in `docs/assets/`. Every figure on screen is measured during
  the run or quoted from Compatibility & Performance and labelled so.
- [`scripts/erp_screenshots.py`][repo-erp-shots] renders the navigation and list screenshots
  from the ERP example with an in-memory database.

The same ERP example runs as the [live demo](demo.md), reset nightly from freshly seeded data
by [`demo.yml`][repo-demo-ci].

## Security checks

- `poe security-check` runs `pip-audit` on the installed dependencies and `pip-licenses`
  (see [`pyproject.toml`][repo-pyproject]). CI runs it on the highest-resolution rows of
  [`test.yml`][repo-test]; the pre-push hook runs it too. Each ignored advisory is listed in
  `pyproject.toml` with the reason.
- Ruff runs the `flake8-bandit` rules (`S`) on every commit.

[repo-unit]: https://github.com/yevheniidehtiar/hyper-admin/tree/develop/tests/unit
[repo-reports]: https://github.com/yevheniidehtiar/hyper-admin/tree/develop/plugins/hyperadmin-reports/tests
[repo-tasks]: https://github.com/yevheniidehtiar/hyper-admin/tree/develop/plugins/hyperadmin-tasks/tests
[repo-logfire]: https://github.com/yevheniidehtiar/hyper-admin/tree/develop/plugins/hyperadmin-logfire/tests
[repo-e2e]: https://github.com/yevheniidehtiar/hyper-admin/tree/develop/tests/e2e
[repo-e2e-apps]: https://github.com/yevheniidehtiar/hyper-admin/tree/develop/tests/e2e/apps
[repo-ci]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/.github/workflows/ci.yml
[repo-test]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/.github/workflows/test.yml
[repo-loadtest-ci]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/.github/workflows/loadtest.yml
[repo-demo-ci]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/.github/workflows/demo.yml
[repo-pyproject]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/pyproject.toml
[repo-precommit]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/.pre-commit-config.yaml
[repo-codecov]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/codecov.yml
[repo-search-like]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/unit/adapters/test_search_like.py
[repo-visual]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/e2e/test_visual_regression.py
[repo-snapshots]: https://github.com/yevheniidehtiar/hyper-admin/tree/develop/tests/e2e/snapshots
[repo-perm-matrix]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/e2e/test_permissions_matrix.py
[repo-charts]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/e2e/test_chart_visual.py
[repo-e2e-i18n]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/e2e/test_i18n.py
[repo-public-api]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/unit/test_public_api.py
[repo-public-api-snapshot]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/unit/public_api_snapshot.txt
[repo-settings-doc]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/unit/test_settings_documented.py
[repo-locale]: https://github.com/yevheniidehtiar/hyper-admin/tree/develop/src/hyperadmin/locale
[repo-i18n-catalogs]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/unit/test_i18n_catalogs.py
[repo-i18n-v059]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/unit/test_i18n_v059_catalogs.py
[repo-i18n-rtl]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/unit/test_i18n_rtl.py
[repo-i18n-validation]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/tests/unit/test_validation_messages_i18n.py
[repo-baselines]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/examples/erp/loadtest/baselines.py
[repo-loadtest-scale]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/scripts/loadtest_scale.py
[repo-tour]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/scripts/demo_tour_video.py
[repo-erp-shots]: https://github.com/yevheniidehtiar/hyper-admin/blob/develop/scripts/erp_screenshots.py
