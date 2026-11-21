"""Former private home of the filter clause builder; use :mod:`hyperadmin.adapters.filtering`.

Kept so code that imported ``hyperadmin.adapters._filter_clause`` before
``build_clauses`` became public keeps working.
"""

from hyperadmin.adapters.filtering import build_clause, build_clauses

__all__ = ["build_clause", "build_clauses"]
