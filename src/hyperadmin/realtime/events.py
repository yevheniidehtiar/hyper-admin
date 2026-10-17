"""Event envelope for real-time CRUD notifications.

A ``RealtimeEvent`` describes one change to one model instance. Adapters
build it, ``to_bytes()`` turns it into the opaque payload carried by a
``PubSubBackend``, and subscribers rebuild it with ``RealtimeEvent.from_bytes()``.

Primary keys are type-agnostic: ``pk`` accepts ``str``, ``int`` or ``UUID``
and always travels as its ``str()`` form, so a deserialised event carries
``pk`` as ``str``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Union
from uuid import UUID

PrimaryKey = Union[str, int, UUID]  # noqa: UP007 - runtime alias must work on Python 3.10


class RealtimeAction(str, Enum):
    """Kind of change a ``RealtimeEvent`` reports."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


@dataclass(frozen=True)
class RealtimeEvent:
    """A CRUD change to one instance of ``model_name``."""

    model_name: str
    pk: PrimaryKey
    action: RealtimeAction
    html_fragment: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """JSON-safe mapping; ``pk`` is stringified, ``action`` is its value."""
        return {
            "model_name": self.model_name,
            "pk": str(self.pk),
            "action": self.action.value,
            "html_fragment": self.html_fragment,
        }

    def to_bytes(self) -> bytes:
        """UTF-8 JSON payload suitable for ``PubSubBackend.publish()``."""
        return json.dumps(self.to_dict(), separators=(",", ":")).encode()

    @classmethod
    def from_dict(cls, data: object) -> RealtimeEvent:
        """Rebuild an event from ``to_dict()`` output; ``ValueError`` if malformed."""
        if not isinstance(data, dict):
            msg = "RealtimeEvent payload must be a JSON object"
            raise ValueError(msg)
        model_name = data.get("model_name")
        pk = data.get("pk")
        html_fragment = data.get("html_fragment")
        if not isinstance(model_name, str) or not model_name:
            msg = "RealtimeEvent payload needs a non-empty string 'model_name'"
            raise ValueError(msg)
        if not isinstance(pk, str):
            msg = "RealtimeEvent payload needs a string 'pk'"
            raise ValueError(msg)
        if html_fragment is not None and not isinstance(html_fragment, str):
            msg = "RealtimeEvent 'html_fragment' must be a string or null"
            raise ValueError(msg)
        return cls(
            model_name=model_name,
            pk=pk,
            action=RealtimeAction(data.get("action")),
            html_fragment=html_fragment,
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> RealtimeEvent:
        """Inverse of ``to_bytes()``; ``ValueError`` on invalid JSON or shape."""
        try:
            decoded = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            msg = "RealtimeEvent payload is not valid UTF-8 JSON"
            raise ValueError(msg) from exc
        return cls.from_dict(decoded)
