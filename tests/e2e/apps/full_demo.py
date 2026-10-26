"""ASGI entry for ``examples/full-demo/main.py``, importable by the E2E server fixture.

``examples/full-demo`` has a hyphen, so it is not an importable package, and its flat
``main`` module would be shadowed by the repository's own ``main.py``. This shim puts the
example directory on ``sys.path`` and loads its ``main.py`` under a unique module name.
"""

import importlib.util
import sys
from pathlib import Path

_DEMO_DIR = Path(__file__).resolve().parents[3] / "examples" / "full-demo"
sys.path.insert(0, str(_DEMO_DIR))

_spec = importlib.util.spec_from_file_location("full_demo_main", _DEMO_DIR / "main.py")
assert _spec is not None
assert _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules["full_demo_main"] = _module
_spec.loader.exec_module(_module)

app = _module.app
