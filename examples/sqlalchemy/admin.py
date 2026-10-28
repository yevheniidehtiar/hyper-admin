"""Explicit registration of the plain SQLAlchemy models (auto-discovery is #716)."""

from __future__ import annotations

from typing import ClassVar

from examples.sqlalchemy.models import Org, Project
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site


class OrgAdmin(ModelAdmin):
    adapter_class = SQLAlchemyAdapter


class ProjectAdmin(ModelAdmin):
    adapter_class = SQLAlchemyAdapter
    list_filter: ClassVar[list[str]] = ["status", "priority"]


site.register(Org, OrgAdmin)
site.register(Project, ProjectAdmin)
