# Models and contexts

[Documentation](../index.md)

## Models

```python
from shopware_admin import (
    Entity,
    Field,
    ToMany,
    ToOne,
    api_field,
    to_many,
    to_one,
)


class Manufacturer(Entity):
    __entity__ = "product_manufacturer"
    __route__ = "product-manufacturer"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)


class Category(Entity):
    __entity__ = "category"
    __route__ = "category"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)
    active: Field[bool] = api_field("active", default=None)


class ProductBase(Entity):
    __entity__ = "product"
    __route__ = "product"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)
    stock: Field[int] = api_field("stock", default=None, required_on_create=True)
    active: Field[bool | None] = api_field("active", default=None)
    parent_id: Field[str | None] = api_field("parentId", default=None)
    manufacturer: ToOne[Manufacturer] = to_one("manufacturer")
    categories: ToMany[Category] = to_many("categories")


class Product(ProductBase):
    erp_reference: Field[str | None] = api_field(
        json_path=("customFields", "erp_reference"),
        criteria_path="customFields.erp_reference",
        default=None,
    )
```

These are illustrative declarations, not a complete or version-independent
Shopware product schema. Define model classes at module scope so Python can
resolve annotations, including forward references. Field types are resolved
from annotations when first used.

- `__entity__` identifies the DAL entity; `__route__` is its exact API route.
- `Field[T]` gives `T` on instances and `FieldExpression[T]` on classes.
- `ToOne[T]` gives `T | None`; `ToMany[T]` gives `list[T]` on instances.
- On classes, associations reuse the related entity type for typed dotted queries.
  `Product.manufacturer.name` is a field expression; on an instance,
  `product.manufacturer.name` is the returned value.
- `default=None` permits omission from a constructor without making `T` nullable.
  It does not insert or serialize a value when the argument is omitted. This
  parameter controls constructor optionality; concrete value defaults are assigned explicitly.
- A field without an explicit default is required by the typed constructor.
- `required_on_create=True` separately checks required write values at creation.
- `writable=False` allows hydration but rejects assignment and patches.
- Associations are read-only and excluded from constructors by default.

Keep generated base classes and handwritten public subclasses in separate files.
Declare the public models in a context (below), or register them with a plain
client, so associations referring to a base class hydrate into the public subclass.
Duplicate JSON mappings and incompatible
registrations fail explicitly. An added field must already be exposed by Shopware.

Supported values are strict Python scalars, optional unions, typed lists/dicts,
`datetime`, and opaque `Any` values. Numeric strings are not coerced to integers,
and booleans are not accepted as integers. Dedicated money/Decimal codecs and
arbitrary nested value-object codecs are follow-up work.

## Typed contexts

Declare named entity sets once, then access repositories directly:

```python
from shopware_admin import Context, Query, entity_set


class ShopContextBase(Context):
    products = entity_set(Product)
    categories = entity_set(Category)
    manufacturers = entity_set(Manufacturer)


class ShopContext(ShopContextBase):
    def available_products(self) -> Query[Product]:
        return self.products.where(Product.stock > 0)
```

`shop.products` is a `Repository[Product]`, with typed query results, patches,
and autocomplete. The context registers every declared model at construction,
including inherited sets, so related entities hydrate into public subclasses
even before their repositories are accessed. No `models=[Product]` argument is
needed. Constructing a context, accessing an entity set, and building a query
perform no HTTP requests. Entity set properties are read-only.

For a future scaffolder, keep the generated context base and handwritten context
subclass in separate files. The base imports the **public model classes**, such as
`Product`, rather than `ProductBase`. This preserves the extended model types
without overriding inherited repository properties. The handwritten context can
add methods and entity sets. See `examples.context_base` and `examples.context`;
these are handwritten illustrations, not generated runtime models.

`Context` accepts the same connection, authentication, timeout, transport, and
request-context arguments as `Client`. Its optional `models=` argument can
register additional association models without declaring named sets. A plain
`Client` and `client.set(Product)` remain available for existing code.
