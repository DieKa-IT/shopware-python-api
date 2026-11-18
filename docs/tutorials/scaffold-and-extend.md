# Scaffold and extend models

[Documentation](../index.md)

Generate a customer model from your shop, then map `vatIds`: a field exposed by
the API that can be missing from its OpenAPI documentation.
You need Python 3.12+, uv, a checkout of this repository, and a reachable Shopware
Admin API with schema access. This exercise reads schemas and prepares a patch;
it does not write product data.

## Install the development tools

From the repository root:

```bash
uv sync --locked
uv --directory tools/scaffolder sync --locked
```

If your shop requires authentication, set `SHOPWARE_API_CLIENT_ID` and
`SHOPWARE_API_CLIENT_SECRET`, or set `SHOPWARE_API_ACCESS_TOKEN`. Choose one mode.

## Save your shop's schemas

From the repository root, replace the example URL with your shop URL:

```bash
uv --directory tools/scaffolder run shopware-admin-scaffold snapshot \
  --url https://shop.example --output ../../schemas/my-shop
```

The path is relative to the scaffolder directory selected by `--directory`.
The bundle records both OpenAPI and DAL metadata for repeatable generation.

## Generate a customer model and context

```bash
uv --directory tools/scaffolder run shopware-admin-scaffold generate \
  --schema-dir ../../schemas/my-shop \
  --output ../../my_shop_api --package my_shop_api \
  --entity customer --context ShopContext
```

In the repository root, inspect `my_shop_api/models/customer.py` and
`my_shop_api/_generated/model_bases.py`. The public `Customer` inherits the generated
`CustomerBase`. The generated context imports the public model.
Associations to entities outside this selection are omitted with a notice.

## Extend the public model

Shopware exposes customer VAT IDs through the API as `vatIds`, even when the
field is missing from the shop's OpenAPI documentation. In Shopware's
[CustomerDefinition](https://github.com/shopware/shopware/blob/28db6ae4279e0137e697813de695572084c19d70/src/Core/Checkout/Customer/CustomerDefinition.php#L128),
`ListField('vat_ids', 'vatIds', StringField::class)` has both `ApiAware` and
`IgnoreInOpenapiSchema` flags. `vat_ids` is the storage name; `vatIds` is the API
property. The [CustomerEntity](https://github.com/shopware/shopware/blob/28db6ae4279e0137e697813de695572084c19d70/src/Core/Checkout/Customer/CustomerEntity.php#L333)
getter and setter document a nullable array of strings.

This is an existing API field, so you do not need to create a custom field in Shopware.

Check your actual response and generated model first. If `vatIds` is not already
mapped, keep the generated base import in `my_shop_api/models/customer.py` and add:

```python
from shopware_admin import Field, api_field

# Keep the existing CustomerBase import from the generated file.

class Customer(CustomerBase):
    vat_ids: Field[list[str] | None] = api_field("vatIds", default=None)
```

The Python attribute `vat_ids` maps to the top-level JSON property `vatIds`.
Its value is a list of strings or null. `default=None` permits constructor omission
without inserting a null into outgoing payloads. Confirm the returned shape and
write permissions against your shop. If the generator already mapped this field,
use that declaration instead of adding a duplicate mapping.

## Use the extension

Save this as `inspect_model.py` in the repository root:

```python
from shopware_admin import AccessToken
from my_shop_api.context import ShopContext
from my_shop_api.models.customer import Customer

# An illustrative API response; no request is sent.
customer = Customer.from_data({"id": "1" * 32, "vatIds": ["DE123456789"]})
print(customer.vat_ids)  # list[str] | None

with ShopContext("https://shop.example", AccessToken("preview-only")) as shop:
    patch = shop.customers.patch().set(Customer.vat_ids, ["DE123456789"])
    print(shop.customers.prepare_update(customer.id, patch).json)
```

Run `uv run python inspect_model.py`. You should see the VAT ID list and the
payload `{'vatIds': ['DE123456789']}`. The VAT number is illustrative.
Preparing the update makes no HTTP request. The same declaration provides typed
response values, autocomplete, and a patch target without repeating the wire name
in application code. To fetch real data later, use `shop.customers.get(customer_id)`
with valid credentials and read `customer.vat_ids` when a customer is returned.

Run the generation command again with `--force`. Your handwritten public model
remains intact while changed generated files can be replaced.
See [scaffold and regenerate](../how-to/scaffold-models.md) for ongoing maintenance
and [add model fields](../how-to/add-model-fields.md) for other mappings.
