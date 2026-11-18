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

## Map an API-aware field omitted from OpenAPI

Shopware can mark a DAL field as API-aware while explicitly excluding it from
OpenAPI. For example, [Shopware's `CustomerDefinition`](https://github.com/shopware/shopware/blob/28db6ae4279e0137e697813de695572084c19d70/src/Core/Checkout/Customer/CustomerDefinition.php#L128)
declares customer VAT IDs as follows (formatting expanded):

```php
(new ListField('vat_ids', 'vatIds', StringField::class))
    ->addFlags(new ApiAware(), new IgnoreInOpenapiSchema())
    ->setDescription('Unique identity of VAT.'),
```

- `ApiAware` exposes the field through the API.
- `IgnoreInOpenapiSchema` leaves it out of the generated OpenAPI schema.
- `vat_ids` is the storage name; `vatIds` is the API property.
- `ListField` with `StringField::class` describes a list of strings.

The scaffolder starts with fields listed in OpenAPI and enriches them with DAL
metadata. It does not generate fields that are absent from OpenAPI, even if they
are API-aware and present in DAL metadata. Add these fields manually to your
public Python model. Regeneration preserves that handwritten extension.

For customer VAT IDs, keep the existing `CustomerBase` import in your generated
public model file, `models/customer.py`, and add:

```python
from shopware_admin import Field, api_field


class Customer(CustomerBase):
    vat_ids: Field[list[str] | None] = api_field("vatIds", default=None)
```

Shopware's [CustomerEntity getter and setter](https://github.com/shopware/shopware/blob/28db6ae4279e0137e697813de695572084c19d70/src/Core/Checkout/Customer/CustomerEntity.php#L333)
describe a nullable array of strings. `vat_ids` is your Python attribute; the
mapping uses `vatIds` for JSON reads and writes. You are mapping an existing
Shopware field, not creating a custom field.

Register the public `Customer` through your context's `entity_set(Customer)`, then
read or prepare an update using the typed attribute:

```python
customer = shop.customers.get(customer_id)
if customer is not None:
    print(customer.vat_ids)

patch = shop.customers.patch().set(Customer.vat_ids, ["DE123456789"])
print(shop.customers.prepare_update(customer_id, patch).json)
# {"vatIds": ["DE123456789"]}
```

The VAT number is illustrative; preparing the update sends no HTTP request.
Verify write permissions and accepted values against your shop before executing it.
If the field is already mapped in your generated model, use that declaration;
duplicate JSON mappings fail explicitly. For a field that can only be read, set
`writable=False` to allow hydration while rejecting assignment and patches.

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

## Use the public model for custom-field queries

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
