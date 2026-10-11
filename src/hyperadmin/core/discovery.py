import logging
from enum import Enum
from typing import Any, Union, get_args, get_origin

from sqlalchemy import inspect as sa_inspect

from hyperadmin.core.display import get_display_name

logger = logging.getLogger(__name__)


async def build_filter_metadata(
    model: Any, field_names: list[str], adapter: Any
) -> list[dict[str, Any]]:
    """Introspects model fields to build metadata for filter UI.

    Args:
        model: The model class to introspect.
        field_names: List of field names to build metadata for.
        adapter: The adapter instance to use for fetching related objects.

    Returns:
        A list of filter metadata dictionaries.
    """
    metadata = []
    for field_name in field_names:
        if field_name not in model.model_fields:
            continue

        field = model.model_fields[field_name]
        label = getattr(field, "title", None) or field_name.replace("_", " ").title()

        ann = getattr(field, "annotation", None)
        origin = get_origin(ann)
        args = get_args(ann)
        if origin is Union and type(None) in args:
            ann = next(arg for arg in args if arg is not type(None))

        # Boolean filter
        if ann is bool:
            metadata.append(
                {
                    "name": field_name,
                    "label": label,
                    "type": "bool",
                    "choices": [
                        {"value": "true", "label": "Yes"},
                        {"value": "false", "label": "No"},
                    ],
                }
            )
        # Enum filter
        elif isinstance(ann, type) and issubclass(ann, Enum):
            metadata.append(
                {
                    "name": field_name,
                    "label": label,
                    "type": "enum",
                    "choices": [{"value": m.value, "label": str(m)} for m in ann],
                }
            )
        # FK / Relationship filter
        else:
            mapper: Any = sa_inspect(model)
            rel = next((r for r in mapper.relationships if r.key == field_name), None)
            fk_col = next((c for c in mapper.columns if c.key == field_name), None)

            target_model = None
            if rel:
                target_model = rel.mapper.class_
            elif fk_col is not None and fk_col.foreign_keys:
                target_rel = next(
                    (r for r in mapper.relationships if fk_col in r.local_columns), None
                )
                if target_rel:
                    target_model = target_rel.mapper.class_

            if target_model:
                from hyperadmin.adapters.registry import adapter_registry  # noqa: PLC0415

                try:
                    # NOTE: known debt (st-v058-byoa-23 review) — core/ builds a concrete
                    # adapter directly instead of going through adapter.for_model(), which
                    # does not exist yet (lands in st-v058-byoa-21). Do not deepen this.
                    target_adapter_cls = adapter_registry.find_adapter_for_model(target_model)
                    target_adapter = target_adapter_cls(target_model, adapter.engine)
                    related_items, _ = await target_adapter.list(page_size=1000)
                    target_pk = target_adapter.pk
                    choices = []
                    for item in related_items:
                        pk_value = target_pk.value_of(item)
                        if pk_value is None:
                            # Skip rows without a usable pk value instead of
                            # letting to_str() raise (uuid) or coerce to the
                            # literal string "None" (int/str).
                            continue
                        choices.append(
                            {
                                "value": target_pk.to_str(pk_value),
                                "label": get_display_name(item, pk_attr=target_pk.attr),
                            }
                        )
                    metadata.append(
                        {
                            "name": field_name,
                            "label": label,
                            "type": "fk",
                            "choices": choices,
                        }
                    )
                except Exception:
                    logger.exception(f"Failed to build FK filter for {field_name}")

    return metadata
