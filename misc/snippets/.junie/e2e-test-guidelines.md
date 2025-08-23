# E2E Testing and Debugging Guidelines (MCP Browser vs Playwright - Python)

TL;DR Recommendation
- Use Playwright (Python) for automated, repeatable, CI-friendly E2E tests and deep debugging (trace, video, console/network capture).
- Use MCP Browser for quick, exploratory, manual checks during development or when you want the AI assistant to visually inspect pages, DOM, or console output on demand.
- Adopt a hybrid workflow: MCP Browser for rapid triage and interactive inspection; Playwright for codified regression tests and rich debugging artifacts.

---

How They Differ
- MCP Browser
  - Strengths: Fast manual verification, DOM inspection, screenshots, quick reproduction steps with the AI assistant. Great for triaging HTMX swaps and verifying partials visually.
  - Limits: Not a test runner, not suited for CI or coverage metrics, limited automation and assertions.

- Playwright (Python)
  - Strengths: Full E2E automation across Chromium/Firefox/WebKit, robust selectors, tracing/video, network mocking, accessibility checks, parallelization, CI integration. Ideal for HTMX partial updates, Alpine behaviors, and regression suites.
  - Limits: Heavier initial setup, tests must be authored and maintained.

---

Decision Matrix
- Rapid manual check of a UI issue: MCP Browser
- Reproducible bug with steps -> needs regression test: Playwright (Python)
- Cross-browser verification: Playwright (Python)
- Inspect a single partial HTMX response or a swap target quickly: MCP Browser
- Continuous coverage, PR gates, artifacts (trace/video): Playwright (Python)
- Visual sanity check while pairing with the assistant: MCP Browser

---

Project-Scoped Guidance (FastAPI + SQLModel + HTMX + Alpine.js + Tailwind)

Core Principles Alignment
- Progressive enhancement: Ensure forms work with standard POST/GET first. Have Playwright tests cover both no-JS (baseline HTML) and JS-enabled paths.
- HTMX responses: Verify partials don’t contain a full <html> document in HTMX flows.
- Code quality: Keep tests small and focused. Use pytest + Playwright Python with type hints where applicable.

---

MCP Browser Guidelines (Exploratory Debugging)
1. When to use
   - You need a quick look at a page state, DOM, or console errors.
   - Validate an HTMX swap result, target containment, or client-side error in Alpine hooks.
   - Triage styling issues in Tailwind components.

2. What to request from the assistant
   - Open the URL /admin/... page and capture:
     - Screenshot at key states (before and after actions)
     - Page HTML snippets for the swapped region (hx-target)
     - Console logs and network requests around the action
   - Execute steps such as:
     - Fill a form, click a button with hx-post/hx-delete
     - Wait for htmx:afterSwap and then capture DOM
   - Ask to emulate viewport/device if responsive bugs are suspected.

3. What to look for (HTMX/Alpine specifics)
   - HTMX headers present in requests: HX-Request, HX-Target
   - Response content type and absence of full-page HTML in partials
   - Correct hx-swap behavior (e.g., outerHTML vs innerHTML)
   - Alpine errors in console (common during x-data init, x-model bindings)
   - Tailwind class conflicts or specificity issues

4. Good triage checklist
   - Can we reproduce on a blank profile?
   - Are CSRF tokens present on form submissions?
   - Does the endpoint return 200 and expected partial HTML?
   - Are event hooks firing (htmx:beforeRequest, htmx:afterSwap)?

---

Playwright Guidelines (Automated Testing & Deep Debugging) — Python

Setup
- Install Playwright Python and browsers:
  - pip install pytest-playwright
  - playwright install
- Run tests against your FastAPI dev server; pass base URL:
  - pytest --base-url=http://localhost:8000 \
           --tracing=retain-on-failure \
           --video=retain-on-failure \
           --screenshot=only-on-failure
- Multi-browser runs:
  - pytest --browser chromium --browser firefox --browser webkit
- In CI, you can set PYTEST_ADDOPTS to include the flags above.

Recommended structure
- Organize tests by pages (list/create/edit) and partials/components under tests/e2e/.
- Keep files small (<150 LOC) per guideline.
- Prefer accessible selectors: get_by_role, get_by_label.

Patterns for HTMX (Python)
```python
import re
from playwright.sync_api import Page, expect

def test_htmx_create_user_updates_list(page: Page) -> None:
    page.goto("/admin/users")

    # Submit the create form (progressive enhancement: JS-enabled)
    page.get_by_label("Name").fill("Alice")
    page.get_by_role("button", name=re.compile("create", re.I)).click()

    # Assert that a new row appears in the target table container
    row = page.locator("#user-list tr", has_text="Alice")
    expect(row).to_be_visible()
```

Validate HTMX partial responses on the network layer
```python
import re
from playwright.sync_api import Page

def test_htmx_partial_response(page: Page) -> None:
    page.goto("/admin/users")
    with page.expect_response(lambda r: 
        "/admin/users" in r.url and r.request.method == "POST"
    ) as resp_info:
        page.get_by_role("button", name=re.compile("create", re.I)).click()
    resp = resp_info.value
    body = resp.text()
    assert not re.search(r"<html[^>]*>", body, re.IGNORECASE)  # Must be partial
```

Confirm swap target and mode
- Check the specific container updated by hx-target and hx-swap (outerHTML vs innerHTML) by asserting DOM changes in the target container only.

Patterns for Alpine.js (Python)
```python
from playwright.sync_api import Page, expect

def test_alpine_inline_validation(page: Page) -> None:
    page.goto("/admin/users")
    name = page.get_by_label("Name")
    name.fill("")
    name.blur()
    expect(page.get_by_text("name is required")).to_be_visible()
```
- For complex components, assert model-driven DOM updates via stable attributes (data-testid) where appropriate.

Tailwind/UI Checks
- Smoke-test critical classes toggled by state changes using locator.evaluate() or by checking class attributes.
- Optional: add visual snapshot tests per component or page (mask dynamic content).

Accessibility (Python)
- Option A: Use axe-playwright-python (optional dependency) to run Axe:
  - pip install axe-playwright-python
  - Example:
```python
from playwright.sync_api import Page
from axe_playwright_python import Axe  # see project docs for latest import path

def test_users_list_accessible(page: Page) -> None:
    page.goto("/admin/users")
    axe = Axe(page)
    results = axe.run()
    assert results["violations"] == []
```
- Option B: Use page.accessibility.snapshot() to spot-check roles/names for critical widgets.

Network, Auth, and CSRF
- Mock or assert CSRF tokens for form posts where applicable.
- Use storage state for authenticated routes or seed a test user via a backend fixture endpoint.

Artifacts and Debugging
- Always collect trace on failures: use --tracing=retain-on-failure and review with: playwright show-trace trace.zip
- Store artifacts per CI job for later inspection (videos, screenshots, traces).

---

Hybrid Workflow (Recommended)
1. Local Dev
   - Reproduce with MCP Browser to see the problem fast and capture DOM/console.
   - If it’s a bug, write a minimal Playwright Python test that fails.
   - Fix server or template, then confirm Playwright passes and artifacts are clean.

2. CI
   - Run Playwright on PRs with headless browsers across all projects.
   - Gate merges on Playwright success and zero accessibility violations for covered pages.

3. Regression Library
   - For each fixed bug, add/keep a Playwright test; keep MCP Browser for ad-hoc checks.

---

Test Ideas Specific to This Stack
- Progressive enhancement:
  - With JS: HTMX swaps update target containers.
  - Without JS: Standard POST redirects to list page; response is full HTML.
- HTMX Events:
  - After create/edit/delete, target container updated and partial lacks <html> tag.
  - hx-confirm prompts before delete; element removed on confirm.
- Alpine Forms:
  - Inline validation messages appear/disappear on blur and submit.
  - Loading states disable buttons and update labels (e.g., “Saving…”).
- Tailwind Classes:
  - Correct classes applied for primary vs. secondary button states.
- Performance:
  - Lists use pagination; query parameter changes update only results area (HTMX get).

---

Common Pitfalls and How to Avoid Them
- Asserting on brittle CSS selectors. Prefer roles/labels/testids.
- Not waiting for network/DOM stabilization in HTMX flows. Rely on expected DOM outcomes, not sleeps.
- Returning full-page templates to HTMX requests. Ensure server detects HX-Request header and returns partials.
- Alpine errors swallowed in console. Always review console logs in traces (Playwright) or MCP output.
- Tailwind purge misconfiguration causing missing classes. Verify production build paths and test a production build in at least one CI job.

---

Minimal Playwright Test Template (Python)
```python
from playwright.sync_api import Page, expect

def test_create_user_via_htmx_partial_update(page: Page) -> None:
    page.goto("/admin/users")

    page.get_by_label("Name").fill("Alice")
    page.get_by_label("Email").fill("alice@example.com")
    page.get_by_role("button", name="Create").click()

    expect(page.locator("#user-list")).to_contain_text("Alice")
```

---

When You Ask Me to Help
- For MCP Browser tasks, tell me:
  - The exact URL/path, steps to reproduce, and what to capture (screenshot, HTML of #user-list, console, network entry for POST /admin/users, etc.).
- For Playwright tasks (Python), tell me:
  - The scenario, selectors you expect to use, and any auth/fixtures. I can draft tests following the file-size and component-decoupling rules.

---

Final Verdict
- If you need rigorous, repeatable testing with CI and rich debugging artifacts: choose Playwright (Python).
- If you want fast exploratory inspection guided by the assistant: choose MCP Browser.
- Use both together: MCP Browser to understand and reproduce, Playwright to prevent regressions and document the fix in code.


---

## Project pytest fixtures (Playwright + FastAPI)

To scale E2E coverage consistently across tests, this repo provides shared pytest fixtures under `tests/e2e/conftest.py`.

- e2e_port (function scope)
  - Returns a free localhost port (int) for the demo server.

- demo_base_url (function scope)
  - Starts `demo_app.main:app` via `uvicorn` on `e2e_port`.
  - Waits until `/admin/` returns HTTP 200.
  - Yields the base URL, e.g., `http://127.0.0.1:PORT`.
  - Gracefully shuts down the subprocess on fixture teardown.
  - Skips if optional dependencies are missing (uvicorn, requests).

- e2e_page (function scope)
  - Yields a Playwright `Page` that records video using our utility `tests/e2e/utils.video_page`.
  - Stores videos under `e2e/artifacts/videos`.
  - Skips if Playwright is not installed.

Example test using fixtures
```python
from playwright.sync_api import expect, Page

def test_admin_dashboard_smoke(e2e_page: Page, demo_base_url: str) -> None:
    e2e_page.goto(demo_base_url + "/admin/")
    expect(e2e_page.get_by_text("Admin Dashboard").first).to_be_visible()
```

Notes
- Existing tests may continue using the `@record_video(param="page")` decorator + custom `run_server` for minimal diffs. New tests should prefer the `e2e_page` and `demo_base_url` fixtures for consistency.
- Prefer accessible selectors (roles/labels) per project guidelines.

Recommended commands
- Install Playwright browsers:
  - `uv run python -m playwright install`
- Run E2E tests with artifacts on failure:
  - `uv run pytest -k e2e -vv`
- Optional (cross-browser, if configured):
  - `uv run pytest --browser chromium --browser firefox --browser webkit`
