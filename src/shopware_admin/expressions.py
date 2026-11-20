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
    from .criteria import Patch
    from .mapping import Entity, Field

E = TypeVar("E", bound="Entity")
T = TypeVar("T")


def _snapshot(value: Any) -> str:
    try:
        return json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise QueryError("Criteria must contain finite JSON values") from error


@dataclass(frozen=True, eq=False)
class Predicate:
    """An immutable filter; combine with &, |, and ~ rather than Python booleans."""

    entity: str
    _json: str

    @classmethod
    def build(cls, entity: str, payload: dict[str, Any]) -> Predicate:
        """Snapshot a raw Shopware filter payload for the specified root entity."""
        return cls(entity, _snapshot(payload))

    def to_payload(self) -> dict[str, Any]:
        """Return a fresh copy of the compiled Shopware filter."""
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
        """Combine two predicates from the same root entity with AND."""
        return self._combine(other, "AND")

    def __or__(self, other: Predicate) -> Predicate:
        """Combine two predicates from the same root entity with OR."""
        return self._combine(other, "OR")

    def __invert__(self) -> Predicate:
        """Negate this predicate using a Shopware not filter."""
        return Predicate.build(
            self.entity, {"type": "not", "operator": "AND", "queries": [self.to_payload()]}
        )

    def __bool__(self) -> Never:
        raise QueryError("Use &, |, and ~ with parentheses, or multiple where() arguments")


@dataclass(frozen=True)
class Sort:
    """An immutable field sort with direction and optional natural ordering."""

    entity: str
    field: str
    order: str
    natural: bool = False

    def to_payload(self) -> dict[str, Any]:
        """Return the Shopware sorting payload for this expression."""
        return {"field": self.field, "order": self.order, "naturalSorting": self.natural}


@dataclass(frozen=True, eq=False)
class FieldExpression(Generic[E, T]):
    """A typed model field path used in filters, sorts, and direct-field patches."""

    root: type[E]
    path: str
    descriptor: Field[T]

    def set(self, value: T) -> Patch[E]:
        """Describe an explicit assignment without sending an HTTP request."""
        from .criteria import Patch

        return Patch(self.root).set(self, value)

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
        """Build an equality filter; use eq() for stricter static operand checking."""
        return self._predicate("equals", value)

    def __ne__(self, value: object) -> Predicate:  # type: ignore[override]
        """Build a negated equality filter."""
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
        """Build an exclusive upper bound for a numeric or datetime field."""
        return self._range("lt", value)

    def __le__(self, value: T) -> Predicate:
        """Build an inclusive upper bound for a numeric or datetime field."""
        return self._range("lte", value)

    def __gt__(self, value: T) -> Predicate:
        """Build an exclusive lower bound for a numeric or datetime field."""
        return self._range("gt", value)

    def __ge__(self, value: T) -> Predicate:
        """Build an inclusive lower bound for a numeric or datetime field."""
        return self._range("gte", value)

    def in_(self, values: list[T] | tuple[T, ...]) -> Predicate:
        """Match any value in a nonempty list or tuple of typed field values."""
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
        """Match a string field containing the supplied substring."""
        self._require_type((str,))
        return self._predicate("contains", value)

    def startswith(self, value: str) -> Predicate:
        """Match a string field beginning with the supplied prefix."""
        self._require_type((str,))
        return self._predicate("prefix", value)

    def endswith(self, value: str) -> Predicate:
        """Match a string field ending with the supplied suffix."""
        self._require_type((str,))
        return self._predicate("suffix", value)

    def is_null(self) -> Predicate:
        """Match JSON null; the field declaration must permit None."""
        return self._predicate("equals", None)

    def asc(self, *, natural: bool = False) -> Sort:
        """Sort ascending, optionally using natural ordering."""
        return Sort(self.root.__entity__, self.path, "ASC", natural)

    def desc(self, *, natural: bool = False) -> Sort:
        """Sort descending, optionally using natural ordering."""
        return Sort(self.root.__entity__, self.path, "DESC", natural)

    def __bool__(self) -> Never:
        raise QueryError("Compare the field explicitly")
