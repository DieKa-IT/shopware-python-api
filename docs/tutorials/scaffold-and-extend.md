# Scaffold and extend models

[Documentation](../index.md)

Generate a product model from your shop, then add an application-specific field.
You need Python 3.12+, uv, a checkout of this repository, and a reachable Shopware
Admin API with schema access. This exercise reads schemas and prepares a query;
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

## Generate a product model and context

```bash
uv --directory tools/scaffolder run shopware-admin-scaffold generate \
  --schema-dir ../../schemas/my-shop \
  --output ../../my_shop_api --package my_shop_api \
  --entity product --context ShopContext
```

In the repository root, inspect `my_shop_api/models/product.py` and
`my_shop_api/_generated/model_bases.py`. The public `Product` inherits the generated
`ProductBase`. The generated context imports the public model.
Associations to entities outside this selection are omitted with a notice.

## Extend the public model

Suppose your shop already exposes a string custom field called `erp_reference`.
In `my_shop_api/models/product.py`, keep its generated base import and add:

```python
from shopware_admin import Field, api_field

# Keep the existing ProductBase import from the generated file.

class Product(ProductBase):
    erp_reference: Field[str | None] = api_field(
        json_path=("customFields", "erp_reference"),
        criteria_path="customFields.erp_reference",
        default=None,
    )
```

This declares a mapping; it does not create the custom field in Shopware.
Dynamic custom-field names may be absent from schema metadata, so this extension
belongs to your application.

## Use the extension

Save this as `inspect_model.py` in the repository root:

```python
from shopware_admin import AccessToken
from my_shop_api.context import ShopContext
from my_shop_api.models.product import Product

with ShopContext("https://shop.example", AccessToken("preview-only")) as shop:
    query = shop.products.where(Product.erp_reference == "ERP-4711")
    print(query.prepare().json)
```

Run `uv run python inspect_model.py`. Preparing the query makes no HTTP request;
you should see a filter using `customFields.erp_reference`.

Run the generation command again with `--force`. Your handwritten public model
remains intact while changed generated files can be replaced.
See [scaffold and regenerate](../how-to/scaffold-models.md) for ongoing maintenance
and [add model fields](../how-to/add-model-fields.md) for other mappings.
