"""Small, immutable expression tree compiled directly to Shopware filters."""

from __future__ import annotations

import json
import types
from dataclasses import dataclass
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Never,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

from .errors import QueryError

if TYPE_CHECKING:
    from .mapping import Entity, Field

T = TypeVar("T")


def _snapshot(value: Any) -> str:
    try:
        return json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise QueryError("Criteria must contain finite JSON values") from error


@dataclass(frozen=True, eq=False)
class Predicate:
    entity: str
    _json: str

    @classmethod
    def build(cls, entity: str, payload: dict[str, Any]) -> Predicate:
        return cls(entity, _snapshot(payload))

    def to_payload(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self._json))

    def _combine(self, other: Predicate, operator: str) -> Predicate:
        if not isinstance(other, Predicate) or other.entity != self.entity:
            raise QueryError("Combine predicates from the same root entity")
        return Predicate.build(
            self.entity,
            {
                "type": "multi",
                "operator": operator,
                "queries": [self.to_payload(), other.to_payload()],
            },
        )

    def __and__(self, other: Predicate) -> Predicate:
        return self._combine(other, "AND")

    def __or__(self, other: Predicate) -> Predicate:
        return self._combine(other, "OR")

    def __invert__(self) -> Predicate:
        return Predicate.build(
            self.entity, {"type": "not", "operator": "AND", "queries": [self.to_payload()]}
        )

    def __bool__(self) -> Never:
        raise QueryError("Use &, |, and ~ with parentheses, or multiple where() arguments")


@dataclass(frozen=True)
class Sort:
    entity: str
    field: str
    order: str
    natural: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {"field": self.field, "order": self.order, "naturalSorting": self.natural}


@dataclass(frozen=True, eq=False)
class FieldExpression(Generic[T]):
    root: type[Entity]
    path: str
    descriptor: Field[T]

    def _predicate(self, kind: str, value: Any) -> Predicate:
        from .mapping import Entity, _encode

        if isinstance(value, FieldExpression) or (
            isinstance(value, type) and issubclass(value, Entity)
        ):
            raise QueryError("Shopware criteria do not support field-to-field comparisons")
        converted = self.descriptor.validate(value)
        return Predicate.build(
            self.root.__entity__, {"type": kind, "field": self.path, "value": _encode(converted)}
        )

    def eq(self, value: T) -> Predicate:
        """Typed alternative to ==; Python's equality protocol accepts object."""
        return self._predicate("equals", value)

    def __eq__(self, value: object) -> Predicate:  # type: ignore[override]
        return self._predicate("equals", value)

    def __ne__(self, value: object) -> Predicate:  # type: ignore[override]
        return ~self._predicate("equals", value)

    def _require_type(self, allowed: tuple[type[Any], ...]) -> None:
        expected = self.descriptor.value_type
        options = (
            get_args(expected) if get_origin(expected) in (Union, types.UnionType) else (expected,)
        )
        if not options or any(option not in (*allowed, type(None)) for option in options):
            raise QueryError(f"Operation is unsupported for {expected}")

    def _range(self, operator: str, value: T) -> Predicate:
        from .mapping import Entity, _encode

        self._require_type((int, float, datetime))
        if (
            value is None
            or isinstance(value, FieldExpression)
            or (isinstance(value, type) and issubclass(value, Entity))
        ):
            raise QueryError("Range comparisons require a scalar value")
        converted = self.descriptor.validate(value)
        return Predicate.build(
            self.root.__entity__,
            {"type": "range", "field": self.path, "parameters": {operator: _encode(converted)}},
        )

    def __lt__(self, value: T) -> Predicate:
        return self._range("lt", value)

    def __le__(self, value: T) -> Predicate:
        return self._range("lte", value)

    def __gt__(self, value: T) -> Predicate:
        return self._range("gt", value)

    def __ge__(self, value: T) -> Predicate:
        return self._range("gte", value)

    def in_(self, values: list[T] | tuple[T, ...]) -> Predicate:
        from .mapping import _encode

        if not values:
            raise QueryError("in_() requires at least one value")
        return Predicate.build(
            self.root.__entity__,
            {
                "type": "equalsAny",
                "field": self.path,
                "value": [_encode(self.descriptor.validate(value)) for value in values],
            },
        )

    def contains(self, value: str) -> Predicate:
        self._require_type((str,))
        return self._predicate("contains", value)

    def startswith(self, value: str) -> Predicate:
        self._require_type((str,))
        return self._predicate("prefix", value)

    def endswith(self, value: str) -> Predicate:
        self._require_type((str,))
        return self._predicate("suffix", value)

    def is_null(self) -> Predicate:
        return self._predicate("equals", None)

    def asc(self, *, natural: bool = False) -> Sort:
        return Sort(self.root.__entity__, self.path, "ASC", natural)

    def desc(self, *, natural: bool = False) -> Sort:
        return Sort(self.root.__entity__, self.path, "DESC", natural)

    def __bool__(self) -> Never:
        raise QueryError("Compare the field explicitly")
