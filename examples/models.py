"""Illustrate the future generated-base / handwritten-subclass contract."""

from __future__ import annotations

from shopware_admin import (
    Entity,
    Field,
    ToMany,
    ToOne,
    api_field,
    to_many,
    to_one,
)


class Media(Entity):
    __entity__ = "media"
    __route__ = "media"

    id: Field[str] = api_field("id", default=None)
    url: Field[str | None] = api_field("url", default=None)
    path: Field[str] = api_field("path", default=None)


class Manufacturer(Entity):
    __entity__ = "product_manufacturer"
    __route__ = "product-manufacturer"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)
    media: ToOne[Media] = to_one("media")


class Category(Entity):
    __entity__ = "category"
    __route__ = "category"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)
    active: Field[bool] = api_field("active", default=None)
    parent: ToOne[Category] = to_one("parent")


class ProductBase(Entity):
    __entity__ = "product"
    __route__ = "product"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)
    product_number: Field[str] = api_field("productNumber", default=None, required_on_create=True)
    stock: Field[int] = api_field("stock", default=None, required_on_create=True)
    tax_id: Field[str] = api_field("taxId", default=None, required_on_create=True)
    price: Field[list[dict[str, str | int | float | bool]]] = api_field(
        "price", default=None, required_on_create=True
    )
    active: Field[bool | None] = api_field("active", default=None)
    parent_id: Field[str | None] = api_field("parentId", default=None)
    created_at: Field[str] = api_field("createdAt", writable=False, init=False)
    manufacturer: ToOne[Manufacturer] = to_one("manufacturer")
    categories: ToMany[Category] = to_many("categories")


class Product(ProductBase):
    erp_reference: Field[str | None] = api_field(
        json_path=("customFields", "erp_reference"),
        criteria_path="customFields.erp_reference",
        default=None,
    )
