"""Declarative, typed entity sets for reusable shop contexts."""

from __future__ import annotations

from typing import Any, Generic, Never, TypeVar, overload

from .client import Client, Repository
from .errors import MappingError
from .mapping import Entity

E_co = TypeVar("E_co", bound=Entity, covariant=True)


class Context(Client):
    """A client that automatically registers models declared with entity_set()."""

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        for name, value in vars(cls).items():
            if isinstance(value, EntitySet) and (
                name.startswith("_") or name in vars(Client) or name in {"context", "registry"}
            ):
                raise MappingError(f"Entity set {name!r} conflicts with the client API")

    @classmethod
    def _declared_models(cls) -> list[type[Entity]]:
        # Merge namespaces in MRO order so overrides and ordinary shadowing agree
        # with Python attribute lookup, including in multiply inherited contexts.
        members: dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            members.update(vars(base))
        return [value.model for value in members.values() if isinstance(value, EntitySet)]


class EntitySet(Generic[E_co]):
    """A read-only declaration returning a repository bound to the accessing context."""

    def __init__(self, model: type[E_co]) -> None:
        if not isinstance(model, type) or not issubclass(model, Entity):
            raise MappingError("Entity sets require an Entity model class")
        self._model = model

    @property
    def model(self) -> type[E_co]:
        return self._model

    @overload
    def __get__(self, instance: None, owner: type[Context]) -> EntitySet[E_co]: ...

    @overload
    def __get__(
        self, instance: Context, owner: type[Context] | None = None
    ) -> Repository[E_co]: ...

    def __get__(
        self, instance: Context | None, owner: type[Context] | None = None
    ) -> EntitySet[E_co] | Repository[E_co]:
        if instance is None:
            return self
        return instance.set(self._model)

    def __set__(self, instance: Context, value: Never) -> Never:
        raise AttributeError("Entity sets are read-only")


def entity_set(model: type[E_co]) -> EntitySet[E_co]:
    """Declare a named repository and automatically register its public model."""
    return EntitySet(model)
