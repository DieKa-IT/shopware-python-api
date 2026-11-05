"""Explicit selection and one-level related entity expansion."""

from . import ScaffoldError
from .catalog import Catalog, EntitySpec
from .naming import pascal_case


def select(
    catalog: Catalog, names: list[str], all_entities: bool = False, related: bool = False
) -> tuple[EntitySpec, ...]:
    if all_entities == bool(names):
        raise ScaffoldError("Specify either --entity or --all")
    chosen: dict[str, EntitySpec] = {}
    if all_entities:
        chosen = {entity.name: entity for entity in catalog.entities}
    else:
        for name in names:
            matches = [
                entity
                for entity in catalog.entities
                if name.casefold()
                in {
                    entity.name.casefold(),
                    entity.route.casefold(),
                    entity.schema_name.casefold(),
                    pascal_case(entity.schema_name).casefold(),
                }
            ]
            if len(matches) != 1:
                raise ScaffoldError(f"Entity {name!r} is missing or ambiguous; use list --filter")
            chosen[matches[0].name] = matches[0]
    if related:
        targets = {
            field.target for entity in chosen.values() for field in entity.fields if field.target
        }
        for entity in catalog.entities:
            if entity.name in targets:
                chosen[entity.name] = entity
    for entity in chosen.values():
        if entity.unsupported:
            raise ScaffoldError(
                f"{entity.name}: {entity.unsupported}; select supported entities explicitly"
            )
    return tuple(sorted(chosen.values(), key=lambda entity: entity.name))
