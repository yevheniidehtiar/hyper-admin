"""Pydantic Logfire observability for HyperAdmin."""

from hyperadmin_logfire.instrument import instrument_admin
from hyperadmin_logfire.plugin import LogfirePlugin

__all__ = ["LogfirePlugin", "instrument_admin"]
