"""Admin registration for ERP custom report views.

This module is intentionally lightweight — the P&L route is already registered
directly on the FastAPI app via ``reports_router`` in ``main.py``.  This file
exists so the ``reports`` package follows the same convention as the other ERP
sub-packages (``contacts``, ``sales``, ``purchases``, ``accounting``), and to
serve as the canonical place to add further report registrations in the future.

The sidebar nav item is added in ``main.py`` after ``admin.mount()`` because
``nav_items`` is only available once the HyperAdmin router has been initialised.
"""
