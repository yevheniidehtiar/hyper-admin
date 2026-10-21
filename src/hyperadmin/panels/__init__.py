"""Bundled detail-page panel factories (``docs/specs/detail-panels.md``).

Each factory returns a :class:`~hyperadmin.core.panels.PanelDef` ready for
``AdminOptions(panels=[...])``. The package imports ``core/`` and never the
reverse (CONSTITUTION §2); ``hyperadmin.__init__`` re-exports its names.
"""

from hyperadmin.panels.pdf import PDFStreamPanel, pdf_stream_panel, pdf_stream_response

__all__ = ["PDFStreamPanel", "pdf_stream_panel", "pdf_stream_response"]
