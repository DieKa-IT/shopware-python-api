# Add missing or custom fields to a model

[Documentation](../index.md)

Use a handwritten public model extension when Shopware exposes a field that your
model does not declare. This can happen with incomplete schemas, plugins, or
dynamic custom fields. A declaration cannot make an unavailable field accessible.

## Verify the API contract

Inspect an actual response from your shop. `product.raw_data` includes unknown
fields and returns a copy of the original response. Confirm the JSON location,
possible value types, nullability, and whether the API allows writing the field.
Confirm filter support and its criteria path separately: response presence alone
does not prove a field is queryable or writable.

## Map a top-level field

Add the declaration to the public subclass, keeping your existing base import:

```python
from shopware_admin import Field, api_field


class Product(ProductBase):
    external_reference: Field[str | None] = api_field(
        "externalReference", default=None, writable=False,
    )
```

Here `externalReference` is illustrative: use the actual name and type exposed by
your installation. `writable=False` allows reads while rejecting assignment and
patches. Remove it only if writes are supported. Do not redeclare an existing JSON
mapping under another attribute; duplicate mappings fail explicitly.

## Map a nested custom field

For a string custom field already configured in Shopware:

```python
class Product(ProductBase):
    erp_reference: Field[str | None] = api_field(
        json_path=("customFields", "erp_reference"),
        criteria_path="customFields.erp_reference",
        default=None,
    )
```

`json_path` controls reading and payload serialization. `criteria_path` controls
query filters. Plugin fields nested under `extensions` may use a different DAL
criteria name; verify both paths rather than deriving one from the other.

`Field[str | None]` permits null. `default=None` permits constructor omission; it
neither inserts a value nor makes a nonnullable type nullable.

## Use the public model everywhere

Ensure the context declares `entity_set(Product)`, using your public class. With
a plain `Client`, register it through `models=[Product]`. Registration allows
associations referring to a base model to hydrate into the extended public type.

```python
query = shop.products.where(Product.erp_reference == "ERP-4711")
for product in query.fetch_page().items:
    print(product.erp_reference)

patch = shop.products.patch().set(Product.erp_reference, "ERP-4712")
print(shop.products.prepare_update(product_id, patch).json)
```

Check the prepared filter and write payload, then verify behavior against your shop.
For nested writes, read the [patch guide](patch-fields.md) before execution.
Keep extensions outside `_generated/` so regeneration preserves them.

See [schema gaps](../explanation/schema-gaps.md) for why handwritten extensions are
part of the design and [models reference](../reference/models.md) for field options.
