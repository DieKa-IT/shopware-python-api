"""Immutable, HTTP-independent criteria and typed explicit patches."""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any, Generic, TypeVar

from .errors import MappingError, QueryError
from .expressions import FieldExpression, Predicate, Sort
from .mapping import Entity, _association_path, _encode, _write_path

E = TypeVar("E", bound=Entity)
R = TypeVar("R", bound=Entity)
T = TypeVar("T")


def _positive(value: int, label: str) -> None:
    if type(value) is not int or value <= 0:
        raise QueryError(f"{label} must be a positive integer")


@dataclass(frozen=True, eq=False)
class Criteria(Generic[E]):
    """Immutable filters, sorts, limits, and association loads for one entity."""

    model: type[E]
    _filters: tuple[Predicate, ...] = ()
    _sorts: tuple[Sort, ...] = ()
    _associations: tuple[tuple[str, Criteria[Any]], ...] = ()
    _limit: int | None = None

    def _check_entity(self, entity: str) -> None:
        if entity != self.model.__entity__:
            raise QueryError("Criteria fields must belong to the queried root entity")

    def where(self, *predicates: Predicate) -> Criteria[E]:
        """Return criteria with additional predicates combined using AND."""
        if not predicates:
            raise QueryError("where() requires at least one predicate")
        for predicate in predicates:
            if not isinstance(predicate, Predicate):
                raise QueryError("where() requires expressions, not Python booleans")
            self._check_entity(predicate.entity)
        return replace(self, _filters=(*self._filters, *predicates))

    def filter(self, *predicates: Predicate) -> Criteria[E]:
        """Alias for where(); return criteria with additional AND-combined predicates."""
        return self.where(*predicates)

    def order_by(self, *sorts: Sort) -> Criteria[E]:
        """Return criteria with sort expressions appended in priority order."""
        for sort in sorts:
            self._check_entity(sort.entity)
        return replace(self, _sorts=(*self._sorts, *sorts))

    def limit(self, size: int) -> Criteria[E]:
        """Return criteria with a positive per-request result limit."""
        _positive(size, "limit")
        return replace(self, _limit=size)

    def load(
        self,
        association: type[R],
        *,
        criteria: Criteria[R] | None = None,
    ) -> Criteria[E]:
        """Include an association, optionally applying criteria to its related entities."""
        selected = _association_path(association)
        self._check_entity(selected.root.__entity__)
        nested = criteria if criteria is not None else Criteria(selected.descriptor.related)
        if nested.model.__entity__ != association.__entity__:
            raise QueryError("Association criteria must query the associated entity")
        if selected.path in dict(self._associations):
            raise QueryError("Configure each association path once")
        return replace(self, _associations=(*self._associations, (selected.path, nested)))

    def to_payload(self) -> dict[str, Any]:
        """Compile criteria into a fresh Shopware search payload without sending it."""
        result: dict[str, Any] = {}
        if self._filters:
            result["filter"] = [predicate.to_payload() for predicate in self._filters]
        if self._sorts:
            result["sort"] = [sort.to_payload() for sort in self._sorts]
        if self._limit is not None:
            result["limit"] = self._limit
        for path, criteria in sorted(self._associations, key=lambda item: item[0].count(".")):
            current = result
            parts = path.split(".")
            for part in parts[:-1]:
                current = current.setdefault("associations", {}).setdefault(part, {})
            associations = current.setdefault("associations", {})
            existing = associations.get(parts[-1], {})
            payload = criteria.to_payload()
            if existing.get("associations"):
                combined = dict(existing["associations"])
                for name, nested in payload.get("associations", {}).items():
                    if name in combined:
                        raise QueryError("Conflicting nested association criteria")
                    combined[name] = nested
                payload["associations"] = combined
            associations[parts[-1]] = payload
        return result


@dataclass(frozen=True, eq=False)
class Patch(Generic[E]):
    """Immutable, typed write selection; only explicitly selected fields are sent."""

    model: type[E]
    _changes: tuple[tuple[tuple[str, ...], Any], ...] = ()

    def set(self, field: FieldExpression[T], value: T) -> Patch[E]:
        """Return a patch setting a writable direct field; explicit None sends JSON null."""
        if field.root.__entity__ != self.model.__entity__:
            raise MappingError("Patch field belongs to another entity")
        descriptor = self.model.__fields__.get(field.descriptor.name)
        if descriptor is not field.descriptor or field.path != descriptor.criteria_path:
            raise MappingError("Patch requires a direct field, not an association traversal")
        if not descriptor.writable:
            raise MappingError(f"{descriptor.name} is read-only")
        converted = _encode(descriptor.validate(value))
        remaining = tuple(item for item in self._changes if item[0] != descriptor.json_path)
        return replace(self, _changes=(*remaining, (descriptor.json_path, converted)))

    def to_payload(self) -> dict[str, Any]:
        """Return a fresh nested JSON payload; reject a patch with no selected fields."""
        if not self._changes:
            raise MappingError("A patch must select at least one field")
        result: dict[str, Any] = {}
        for path, value in self._changes:
            _write_path(result, path, copy.deepcopy(value))
        return result
