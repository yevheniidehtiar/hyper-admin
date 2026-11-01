"""Pure presentation helpers for the task pages: age text, state pills and pagination links."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC
from math import ceil
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from hyperadmin_tasks.backend import TaskState

if TYPE_CHECKING:
    from datetime import datetime, timedelta

_MINUTE = 60
_HOUR = 3600
_DAY = 86400

#: Largest JSON text (in UTF-8 bytes) shown inline before the preview is cut.
PREVIEW_LIMIT = 64 * 1024

#: Pill kind (see ``components/pill.html``) per task state.
STATE_PILL_KIND: dict[TaskState, str] = {
    TaskState.PENDING: "",
    TaskState.SCHEDULED: "info",
    TaskState.RUNNING: "info",
    TaskState.SLEEPING: "",
    TaskState.WAITING: "",
    TaskState.SUCCEEDED: "success",
    TaskState.FAILED: "danger",
    TaskState.CANCELLED: "warning",
}


#: States a task can be retried from, and cancelled from; the retry / cancel buttons show only
#: for these.
RETRYABLE_STATES = frozenset({TaskState.FAILED, TaskState.CANCELLED})
CANCELLABLE_STATES = frozenset({TaskState.PENDING, TaskState.SCHEDULED})


def format_age(age: timedelta | None) -> str | None:
    """Compact text for an age ("45s", "12m", "3h 5m", "2d 4h"); ``None`` stays ``None``."""
    if age is None:
        return None
    seconds = max(int(age.total_seconds()), 0)
    if seconds < _MINUTE:
        return f"{seconds}s"
    if seconds < _HOUR:
        return f"{seconds // _MINUTE}m"
    if seconds < _DAY:
        return f"{seconds // _HOUR}h {seconds % _HOUR // _MINUTE}m"
    return f"{seconds // _DAY}d {seconds % _DAY // _HOUR}h"


def format_utc(moment: datetime | None) -> str | None:
    """``moment`` as ``YYYY-MM-DD HH:MM:SS UTC`` (naive values are taken as UTC)."""
    if moment is None:
        return None
    utc = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
    return f"{utc:%Y-%m-%d %H:%M:%S} UTC"


@dataclass(frozen=True)
class JsonView:
    """Pretty-printed JSON for display; ``truncated`` previews hold only the first bytes."""

    text: str
    truncated: bool
    size: int


def render_json(value: Any, *, full: bool = False) -> JsonView | None:
    """``value`` as indented JSON, cut to :data:`PREVIEW_LIMIT` bytes unless ``full``.

    ``None`` stays ``None``; values JSON cannot represent are shown by their ``str()``. The
    text is plain data: templates escape it, it is never marked safe.
    """
    if value is None:
        return None
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    encoded = text.encode()
    if full or len(encoded) <= PREVIEW_LIMIT:
        return JsonView(text, False, len(encoded))
    return JsonView(encoded[:PREVIEW_LIMIT].decode(errors="ignore"), True, len(encoded))


def list_url(base: str, params: dict[str, str], page: int) -> str:
    """``base`` with the non-empty filter ``params`` and, past page one, ``page``."""
    query = {key: value for key, value in params.items() if value}
    if page > 1:
        query["page"] = str(page)
    return f"{base}?{urlencode(query)}" if query else base


@dataclass(frozen=True)
class Pagination:
    """Where a listing page sits in its result set; ``total`` is ``None`` when unknown."""

    page: int
    per_page: int
    shown: int
    total: int | None

    @property
    def start_index(self) -> int:
        """1-based index of the first row on the page (0 when the page is empty)."""
        return (self.page - 1) * self.per_page + 1 if self.shown else 0

    @property
    def end_index(self) -> int:
        """1-based index of the last row on the page (0 when the page is empty)."""
        return self.start_index + self.shown - 1 if self.shown else 0

    @property
    def total_pages(self) -> int | None:
        """Number of pages, at least one, or ``None`` when the total is unknown."""
        return None if self.total is None else max(ceil(self.total / self.per_page), 1)

    @property
    def has_previous(self) -> bool:
        """Whether a page precedes this one."""
        return self.page > 1

    @property
    def has_next(self) -> bool:
        """Whether a page follows this one (a full page implies one when the total is unknown)."""
        if self.total is None:
            return self.shown >= self.per_page
        return self.page < (self.total_pages or 1)
