"""Filter library: declarative list filters for ``AdminOptions.list_filter``.

Example:
    ```python
    from hyperadmin.filters import DateRangeFilter, IsOwnerFilter

    filters = [DateRangeFilter(field="created_at"), IsOwnerFilter(owner_fields="created_by")]
    ```
"""

from hyperadmin.filters.base import FilterBinding, FilterDef, FilterRenderContext
from hyperadmin.filters.boolean import BooleanFilter, IsOwnerFilter
from hyperadmin.filters.choice import MultiChoiceFilter
from hyperadmin.filters.date import PRESETS, CurrentPeriodDefault, DateRangeFilter, period_bounds
from hyperadmin.filters.relation import MultiFKFilter

__all__ = [
    "PRESETS",
    "BooleanFilter",
    "CurrentPeriodDefault",
    "DateRangeFilter",
    "FilterBinding",
    "FilterDef",
    "FilterRenderContext",
    "IsOwnerFilter",
    "MultiChoiceFilter",
    "MultiFKFilter",
    "period_bounds",
]
