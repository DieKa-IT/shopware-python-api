"""Descriptors are query expressions on classes and typed values on instances."""

from __future__ import annotations

import copy
import math
import types
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import (
    Any,
    ClassVar,
    Generic,
    Literal,
    TypeVar,
    Union,
    dataclass_transform,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from .errors import FieldNotLoadedError, MappingError, QueryError
from .expressions import FieldExpression

T = TypeVar("T")
E = TypeVar("E", bound="Entity")


class _RequiredArgument:
    """Private marker for the field factory's omitted default argument."""


_REQUIRED_ARGUMENT = _RequiredArgument()


@dataclass(frozen=True)
class _AssociationPath:
    root: type[Entity]
    path: str
    descriptor: _AssociationField


def _association_path(model: type[Entity]) -> _AssociationPath:
    if not isinstance(model, type) or not issubclass(model, Entity):
        raise QueryError("Select an association from the queried entity class")
    association = model.__query_path__
    if association is None:
        raise QueryError("Select an association such as Product.manufacturer, not its entity model")
    return association


def _convert(value: Any, expected: Any, *, wire: bool = False) -> Any:
    """Strict scalar validation and recursive JSON container conversion."""
    if expected is Any:
        return copy.deepcopy(value)
    origin = get_origin(expected)
    args = get_args(expected)
    if origin in (Union, types.UnionType):
        for option in args:
            try:
                return _convert(value, option, wire=wire)
            except MappingError:
                pass
        raise MappingError(f"Expected {expected}, received {type(value).__name__}")
    if expected is type(None):
        if value is None:
            return None
    elif origin is list and isinstance(value, list):
        return [_convert(item, args[0], wire=wire) for item in value]
    elif origin is dict and isinstance(value, dict):
        return {
            _convert(key, args[0], wire=wire): _convert(item, args[1], wire=wire)
            for key, item in value.items()
        }
    elif expected is datetime:
        if isinstance(value, datetime):
            return value
        if wire and isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise MappingError("Invalid datetime") from error
    elif expected is float and type(value) in (int, float):
        converted = float(value)
        if not math.isfinite(converted):
            raise MappingError("JSON numbers must be finite")
        return converted
    elif expected in (str, int, bool, float) and type(value) is expected:
        return value
    elif isinstance(expected, type) and isinstance(value, expected):
        if expected not in (int, bool, str, float):
            return value
    raise MappingError(f"Expected {expected}, received {type(value).__name__}")


def _read_path(data: Mapping[str, Any], path: tuple[str, ...]) -> tuple[bool, Any]:
    current: Any = data
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _write_path(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = data
    for part in path[:-1]:
        existing = current.setdefault(part, {})
        if not isinstance(existing, dict):
            raise MappingError(f"Conflicting JSON mappings at {'.'.join(path)}")
        current = existing
    current[path[-1]] = value


def _encode(value: Any) -> Any:
    if isinstance(value, Entity):
        return value.to_payload()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    return copy.deepcopy(value)


class _MappedField:
    def __init__(
        self,
        json_path: tuple[str, ...],
        criteria_path: str,
        *,
        writable: bool,
        required_on_create: bool,
        default: None | _RequiredArgument,
        init: bool,
    ):
        if not json_path or any(not part for part in json_path) or not criteria_path:
            raise MappingError("Fields require nonempty JSON and criteria paths")
        self.json_path = json_path
        self.criteria_path = criteria_path
        self.writable = writable
        self.required_on_create = required_on_create
        self.required_init = init and default is _REQUIRED_ARGUMENT
        self.init = init
        self.name = ""
        self.owner: type[Entity]

    def __set_name__(self, owner: type[Entity], name: str) -> None:
        if self.name and (self.name != name or self.owner is not owner):
            raise MappingError("Declare a new descriptor for each mapped field")
        self.owner = owner
        self.name = name

    @cached_property
    def value_type(self) -> Any:
        try:
            annotation = get_type_hints(self.owner)[self.name]
            args = get_args(annotation)
            if not args:
                raise MappingError(f"Annotate {self.name} as Field[T], ToOne[T], or ToMany[T]")
            return args[0]
        except (NameError, KeyError, TypeError) as error:
            raise MappingError(
                f"Cannot resolve annotation for {self.owner.__name__}.{self.name}"
            ) from error

    @property
    def nullable(self) -> bool:
        expected = self.value_type
        return (
            expected is Any
            or expected is type(None)
            or (
                get_origin(expected) in (Union, types.UnionType)
                and type(None) in get_args(expected)
            )
        )

    def get_value(self, instance: Entity) -> Any:
        if self.name in instance._values:
            return instance._values[self.name]
        # Nullable values can be read as None without adding them to a write payload.
        if self.nullable:
            return None
        raise FieldNotLoadedError(f"{type(instance).__name__}.{self.name} was not loaded")

    def set_value(self, instance: Entity, value: Any) -> None:
        if not self.writable:
            raise MappingError(f"{self.name} is read-only")
        instance._values[self.name] = self.validate(value)

    def validate(self, value: Any, *, wire: bool = False) -> Any:
        return _convert(value, self.value_type, wire=wire)

    def decode(self, value: Any, registry: ModelRegistry) -> Any:
        return self.validate(value, wire=True)


class Field(_MappedField, Generic[T]):
    @overload
    def __get__(self, instance: None, owner: type[Entity]) -> FieldExpression[T]: ...

    @overload
    def __get__(self, instance: Entity, owner: type[Entity]) -> T: ...

    def __get__(self, instance: Entity | None, owner: type[Entity]) -> Any:
        from .expressions import FieldExpression

        if instance is None:
            association = owner.__query_path__
            if association is not None:
                return FieldExpression(
                    association.root, f"{association.path}.{self.criteria_path}", self
                )
            return FieldExpression(owner, self.criteria_path, self)
        return self.get_value(instance)

    def __set__(self, instance: Entity, value: T) -> None:
        self.set_value(instance, value)


class _AssociationField(_MappedField):
    many = False

    @property
    def nullable(self) -> bool:
        return not self.many

    @property
    def related(self) -> type[Entity]:
        target = self.value_type
        if not isinstance(target, type) or not issubclass(target, Entity):
            raise MappingError(f"{self.name} must reference an Entity subclass")
        return target

    def bind(self, owner: type[Entity]) -> type[Entity]:
        association = owner.__query_path__
        root = owner if association is None else association.root
        path = (
            self.criteria_path
            if association is None
            else f"{association.path}.{self.criteria_path}"
        )
        # Reuse the entity's descriptors; only the query path belongs to this private view.
        return type(
            f"_{self.related.__name__}Association",
            (self.related,),
            {
                "__module__": self.related.__module__,
                "__query_path__": _AssociationPath(root, path, self),
            },
        )

    def validate(self, value: Any, *, wire: bool = False) -> Any:
        if self.many:
            if not isinstance(value, list) or any(
                not isinstance(item, self.related) for item in value
            ):
                raise MappingError(f"{self.name} requires a list of {self.related.__name__}")
        elif value is not None and not isinstance(value, self.related):
            raise MappingError(f"{self.name} requires {self.related.__name__} or None")
        return value

    def decode(self, value: Any, registry: ModelRegistry) -> Any:
        model = registry.resolve(self.related)
        if self.many:
            if not isinstance(value, list):
                raise MappingError(f"{self.name} requires a JSON array")
            return [model.from_data(item, registry=registry) for item in value]
        if value is None:
            return None
        return model.from_data(value, registry=registry)


class ToOne(_AssociationField, Generic[E]):
    @overload
    def __get__(self, instance: None, owner: type[Entity]) -> type[E]: ...

    @overload
    def __get__(self, instance: Entity, owner: type[Entity]) -> E | None: ...

    def __get__(self, instance: Entity | None, owner: type[Entity]) -> Any:
        return self.bind(owner) if instance is None else self.get_value(instance)

    def __set__(self, instance: Entity, value: E | None) -> None:
        self.set_value(instance, value)


class ToMany(_AssociationField, Generic[E]):
    many = True

    @overload
    def __get__(self, instance: None, owner: type[Entity]) -> type[E]: ...

    @overload
    def __get__(self, instance: Entity, owner: type[Entity]) -> list[E]: ...

    def __get__(self, instance: Entity | None, owner: type[Entity]) -> Any:
        return self.bind(owner) if instance is None else self.get_value(instance)

    def __set__(self, instance: Entity, value: list[E]) -> None:
        self.set_value(instance, value)


def api_field(
    api_name: str | None = None,
    *,
    json_path: tuple[str, ...] | None = None,
    criteria_path: str | None = None,
    writable: bool = True,
    required_on_create: bool = False,
    default: None | _RequiredArgument = _REQUIRED_ARGUMENT,
    init: bool = True,
) -> Field[Any]:
    """Use default=None to allow omission; only explicitly supplied values are serialized."""
    path = json_path if json_path is not None else ((api_name,) if api_name else ())
    return Field(
        path,
        criteria_path if criteria_path is not None else ".".join(path),
        writable=writable,
        required_on_create=required_on_create,
        default=default,
        init=init,
    )


def to_one(
    api_name: str,
    *,
    json_path: tuple[str, ...] | None = None,
    criteria_path: str | None = None,
    writable: bool = False,
    default: None = None,
    init: Literal[False] = False,
) -> ToOne[Any]:
    return ToOne(
        json_path if json_path is not None else (api_name,),
        criteria_path if criteria_path is not None else api_name,
        writable=writable,
        required_on_create=False,
        default=default,
        init=init,
    )


def to_many(
    api_name: str,
    *,
    json_path: tuple[str, ...] | None = None,
    criteria_path: str | None = None,
    writable: bool = False,
    default: None = None,
    init: Literal[False] = False,
) -> ToMany[Any]:
    return ToMany(
        json_path if json_path is not None else (api_name,),
        criteria_path if criteria_path is not None else api_name,
        writable=writable,
        required_on_create=False,
        default=default,
        init=init,
    )


@dataclass_transform(
    kw_only_default=True, eq_default=False, field_specifiers=(api_field, to_one, to_many)
)
class Entity:
    __entity__: ClassVar[str] = ""
    __route__: ClassVar[str] = ""
    __fields__: ClassVar[dict[str, _MappedField]] = {}
    __query_path__: ClassVar[_AssociationPath | None] = None

    def __init_subclass__(cls) -> None:
        fields: dict[str, _MappedField] = {}
        for base in reversed(cls.__mro__[1:]):
            fields.update(getattr(base, "__fields__", {}))
        for name, value in vars(cls).items():
            if isinstance(value, _MappedField):
                fields[name] = value
            elif name in fields:
                raise MappingError(f"{name} shadows an inherited mapped field")
        paths: set[tuple[str, ...]] = set()
        for field in fields.values():
            if field.json_path in paths:
                raise MappingError(f"Duplicate JSON mapping: {'.'.join(field.json_path)}")
            paths.add(field.json_path)
        cls.__fields__ = fields

    def __init__(self, **values: Any):
        self._values: dict[str, Any] = {}
        self._extras: dict[str, Any] = {}
        for name, field in self.__fields__.items():
            if field.required_init and name not in values:
                raise MappingError(f"Constructor requires {name}")
        for name, value in values.items():
            if name not in self.__fields__:
                raise MappingError(f"Unknown field {type(self).__name__}.{name}")
            self.__fields__[name].set_value(self, value)

    @classmethod
    def from_data(
        cls: type[E], data: Mapping[str, Any], *, registry: ModelRegistry | None = None
    ) -> E:
        if not isinstance(data, Mapping):
            raise MappingError(f"{cls.__name__} requires a JSON object")
        registry = registry if registry is not None else ModelRegistry([cls])
        instance = cls.__new__(cls)
        instance._values = {}
        instance._extras = copy.deepcopy(dict(data))
        for name, field in cls.__fields__.items():
            present, value = _read_path(data, field.json_path)
            if present:
                # Shopware emits null for unloaded to-many associations, and []
                # for loaded collections without members. Keep them distinct.
                if isinstance(field, ToMany) and value is None:
                    continue
                instance._values[name] = field.decode(value, registry)
        return instance

    @property
    def raw_data(self) -> dict[str, Any]:
        """Original response, including unknown fields; never used as a write payload."""
        return copy.deepcopy(self._extras)

    def is_loaded(self, field: FieldExpression[Any] | type[Entity]) -> bool:
        """Whether a direct field was supplied, returned, or subsequently assigned."""
        descriptor: _MappedField
        if isinstance(field, type):
            association = field.__query_path__
            if association is None:
                raise MappingError("Select a direct field or association of this entity")
            root, descriptor, path = association.root, association.descriptor, association.path
        else:
            root, descriptor, path = field.root, field.descriptor, field.path
        if root.__entity__ != self.__entity__ or descriptor.name not in self.__fields__:
            raise MappingError("Field belongs to another entity")
        if self.__fields__[descriptor.name] is not descriptor:
            raise MappingError("Use a direct field of this entity")
        if path != descriptor.criteria_path:
            raise MappingError("Use a direct field of this entity")
        return descriptor.name in self._values

    def to_payload(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, value in self._values.items():
            field = self.__fields__[name]
            if field.writable:
                _write_path(result, field.json_path, _encode(field.validate(value)))
        return result


class ModelRegistry:
    """Resolve generated association targets to public handwritten subclasses."""

    def __init__(self, models: list[type[Entity]] | None = None):
        self._models: dict[str, type[Entity]] = {}
        for model in models or []:
            self.register(model)

    def register(self, model: type[Entity]) -> None:
        if model.__query_path__ is not None:
            raise MappingError(
                "Use the declared entity model for repositories, not an association path"
            )
        if not model.__entity__ or not model.__route__:
            raise MappingError("Models require __entity__ and __route__ metadata")
        existing = self._models.get(model.__entity__)
        if existing is not None and not (
            issubclass(model, existing) or issubclass(existing, model)
        ):
            raise MappingError(f"Conflicting public models for {model.__entity__}")
        if existing is None or issubclass(model, existing):
            self._models[model.__entity__] = model

    def resolve(self, model: type[E]) -> type[E]:
        resolved = self._models.get(model.__entity__, model)
        if not issubclass(resolved, model):
            raise MappingError(f"Registered model is incompatible with {model.__name__}")
        return resolved
