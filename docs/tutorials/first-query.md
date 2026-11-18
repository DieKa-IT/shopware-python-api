# Your first typed query

[Documentation](../index.md)

Build a small model, query it, and preview a stock update. This tutorial uses a mock
HTTP transport, so you need no Shopware instance or credentials.

## Install the library

Use Python 3.12+ in a virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install shopware-admin
```

## Create the example

Save this as `first_query.py`. Define the classes at module scope so their
annotations can be resolved.

```python
import httpx

from shopware_admin import AccessToken, Context, Entity, Field, api_field, entity_set


class Product(Entity):
    __entity__ = "product"
    __route__ = "product"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)
    stock: Field[int] = api_field("stock", default=None)


class ShopContext(Context):
    products = entity_set(Product)


def respond(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={
        "data": [{"id": "1" * 32, "name": "O-ring", "stock": 12}],
        "total": 1,
    })


with ShopContext(
    "https://shop.example",
    AccessToken("demo"),
    transport=httpx.MockTransport(respond),
) as shop:
    query = shop.products.where(Product.stock > 0).order_by(Product.name.asc())
    prepared = query.prepare(size=20)
    print(prepared.path)
    print(prepared.json)

    result = prepared.execute()
    for product in result.items:
        print(product.name, product.stock)

    patch = shop.products.patch().set(Product.stock, 25)
    update = shop.products.prepare_update("1" * 32, patch)
    print(update.json)
```

## Run it

```bash
python first_query.py
```

You should see the search path `/api/search/product`, criteria containing a stock
range filter, `O-ring 12`, and the patch payload `{'stock': 25}`.
The mock always returns the same product; it demonstrates request construction
and hydration rather than server-side filtering. The update is only prepared.

On the class, `Product.stock` builds a query expression. On a returned instance,
`product.stock` is an `int`. Your editor can complete both accesses from the same
declaration. Try changing the patch value to a string: a type checker should
report the mismatch, and runtime validation rejects it too.

## Connect to a shop

To execute the search against a real shop, replace `AccessToken("demo")` with
`IntegrationAuth(client_id, client_secret)` (imported from `shopware_admin`), use
your shop URL, and remove `transport=...`. Supply credentials from your environment.
Your integration needs permission to read products. The model above is a small
read example, not a complete product creation schema.

Continue with [scaffold and extend models](scaffold-and-extend.md), or learn how to
[patch selected fields](../how-to/patch-fields.md).
