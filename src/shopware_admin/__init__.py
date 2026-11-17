"""Typed mappings and Shopware criteria; no runtime schema discovery required."""

from .client import (
    AccessToken,
    Client,
    CountMode,
    IntegrationAuth,
    PreparedRequest,
    Query,
    Repository,
    RequestContext,
    SearchResult,
)
from .context import Context, EntitySet, entity_set
from .criteria import Criteria, Patch
from .errors import (
    CardinalityError,
    FieldNotLoadedError,
    MappingError,
    QueryError,
    ResponseError,
    ShopwareApiError,
    ShopwareError,
    TransportError,
)
from .expressions import FieldExpression, Predicate, Sort
from .mapping import Entity, Field, ModelRegistry, ToMany, ToOne, api_field, to_many, to_one

__all__ = [
    "AccessToken",
    "CardinalityError",
    "Client",
    "Context",
    "CountMode",
    "Criteria",
    "Entity",
    "EntitySet",
    "Field",
    "FieldExpression",
    "FieldNotLoadedError",
    "IntegrationAuth",
    "MappingError",
    "ModelRegistry",
    "Patch",
    "Predicate",
    "PreparedRequest",
    "Query",
    "QueryError",
    "Repository",
    "RequestContext",
    "ResponseError",
    "SearchResult",
    "ShopwareApiError",
    "ShopwareError",
    "Sort",
    "ToMany",
    "ToOne",
    "TransportError",
    "api_field",
    "entity_set",
    "to_many",
    "to_one",
]
