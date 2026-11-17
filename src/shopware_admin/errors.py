"""Exceptions with structured API errors, without credentials in messages."""

from typing import Any


class ShopwareError(Exception):
    """Base library exception."""


class MappingError(ShopwareError, ValueError):
    """Invalid model metadata or a value inconsistent with its field type."""


class FieldNotLoadedError(ShopwareError, AttributeError):
    """A nonnullable field has not been supplied or loaded."""


class QueryError(ShopwareError, ValueError):
    """An expression cannot be represented by Shopware criteria."""


class ResponseError(ShopwareError):
    """A successful HTTP response did not match the expected contract."""


class CardinalityError(ShopwareError):
    """A query expected exactly one result."""


class TransportError(ShopwareError):
    """HTTP transport failed, with no automatic write replay."""


class ShopwareApiError(ShopwareError):
    def __init__(self, method: str, path: str, status: int, errors: list[dict[str, Any]]):
        self.method = method
        self.path = path
        self.status = status
        self.errors = errors
        super().__init__(f"Shopware {method} {path} returned HTTP {status}")
