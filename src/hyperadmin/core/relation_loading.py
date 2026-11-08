"""Decide which relations a list page loads."""

from collections.abc import Collection, Sequence


def resolve_list_relations(
    explicit: Sequence[str] | None,
    column_list: Sequence[str],
    relation_names: Collection[str],
    *,
    auto: bool,
) -> list[str]:
    """Return the relations to load for a list page, without duplicates.

    ``explicit`` (``list_select_related``) comes first. With ``auto`` on, every
    ``column_list`` entry that names a relation, or reaches through one with a dotted
    accessor such as ``"category.name"``, is added after it. Anything else loads nothing.
    """
    resolved = list(dict.fromkeys(explicit or ()))
    if auto:
        for column in column_list:
            relation = column.split(".", 1)[0]
            if relation in relation_names and relation not in resolved:
                resolved.append(relation)
    return resolved
