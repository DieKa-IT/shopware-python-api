# Refresh a T-shirt collection

[Documentation](../index.md)

Use typed Python models to find T-shirts, create a blue one, retrieve it by ID,
change the green one's price, and delete a discontinued design. This tutorial runs
against an in-memory mock shop: no credentials or running Shopware instance are
needed, and every run starts with the same two products.

The T-shirts are standalone products. Modeling actual color variants involves
parent products and option associations and is outside this first workflow.

## Run the complete example

With Python 3.12+, uv, and a checkout of this repository, run from the repository root:

```bash
uv sync --locked
uv run python -m examples.tshirt_collection
```

The complete runnable code is in [examples/tshirt_collection.py](../../examples/tshirt_collection.py).
Its `DemoShop` class supplies just the endpoints and filtering behavior used here.
It holds changes in memory; it is not a full implementation of Shopware's validation
or write semantics. The walkthrough below follows its `refresh_collection()` function.

Expected output includes:

```text
Before:
DEMO-TSHIRT-OLD Discontinued T-shirt 0
DEMO-TSHIRT-GREEN Green T-shirt 12
Created: DEMO-TSHIRT-BLUE Blue T-shirt
Price patch: ...
Updated: DEMO-TSHIRT-GREEN 17.85
Deleted: DEMO-TSHIRT-OLD
After:
DEMO-TSHIRT-BLUE Blue T-shirt 20
DEMO-TSHIRT-GREEN Green T-shirt 12
```

## Understand the model and context

The example imports your application's model and context:

```python
from examples.context import ShopContext
from examples.models import Product
```

The [Product model](../../examples/models.py) maps Python attributes to API fields.
For example:

```python
stock: Field[int] = api_field("stock", default=None, required_on_create=True)
product_number: Field[str] = api_field(
    "productNumber",
    default=None,
    required_on_create=True,
)
```

`Field` and `api_field` come from `shopware_admin`. These declarations belong inside
the model class. `Product.stock` is a query expression; `product.stock` on an
instance is an integer. The same declarations support autocomplete and typed patches.
The context declares `products = entity_set(Product)`, giving us `shop.products`.

These example models are handwritten. The [next tutorial](scaffold-and-extend.md)
shows how to generate models from your shop instead.

## 1. Find the existing T-shirts

```python
query = shop.products.where(Product.name.contains("T-shirt")).order_by(Product.name.asc())
for product in query.fetch_page().items:
    print(product.product_number, product.name, product.stock)
```

Building `query` makes no HTTP request. `fetch_page()` executes it using Shopware's
`POST /api/search/product` endpoint and returns typed products.

We call the Python expression a **query** and its execution a **search**. You do
not have to call `.search()` before `.where()`. Use `shop.products.search()` when
you want an unfiltered query as your starting point.

## 2. Create a blue T-shirt

```python
blue = Product(
    name="Blue T-shirt",
    product_number="DEMO-TSHIRT-BLUE",
    stock=20,
    tax_id=TAX_ID,
    price=euro_price(29.75, 25.00),
)
blue_id = shop.products.create(blue)
```

`create()` sends `POST /api/product`. The library generates an ID locally when you
do not supply one, returns it after success, and fills `blue.id`.

`TAX_ID` and `CURRENCY_ID` are illustrative mock-shop IDs declared in the example.
Its helper builds the currency-specific price structure:

```python
def euro_price(gross: float, net: float) -> list[dict[str, str | int | float | bool]]:
    return [{"currencyId": CURRENCY_ID, "gross": gross, "net": net, "linked": True}]
```

The amounts assume 19% VAT. Both gross and net are supplied explicitly; this helper
does not calculate tax. `price` is a list of currency prices, not a single number.
Only explicitly supplied writable fields are serialized; omission lets the server
apply defaults. This sample supplies the creation requirements declared by its model.

## 3. Retrieve the new product by ID

```python
created = shop.products.get(blue_id)
assert created is not None
print(created.product_number, created.name)
```

Because we already know the ID, use `get()` rather than building a search query.
It sends `GET /api/product/{id}` and returns `Product | None`; HTTP 404 means missing.

## 4. Change the green T-shirt's price

Find the green product by its unique product number:

```python
green = shop.products.where(Product.product_number == "DEMO-TSHIRT-GREEN").one()
```

This executes a search. `.one()` requires exactly one match and raises
`CardinalityError` otherwise, avoiding an arbitrary first match.

Prepare the update, inspect it, then execute it:

```python
patch = shop.products.patch().set(Product.price, euro_price(17.85, 15.00))
update = shop.products.prepare_update(green.id, patch)
print(update.json)
update.execute()
```

The request uses `PATCH /api/product/{id}`. Only `price` is selected for writing;
name and stock are absent from the patch. Preparing makes no request; execution
sends it. The example fetches the product again to verify its changed price.

Supply the intended price list. This example has one currency; it does not show
how to preserve additional currency prices in a real shop. The library provides
no client-side merge guarantee for nested writes.

The current patch interface needs major reworking and may change during alpha;
see [known gaps](../known-gaps.md#patch-api-needs-major-reworking).

## 5. Delete the discontinued design

```python
old = shop.products.where(Product.product_number == "DEMO-TSHIRT-OLD").one()
shop.products.delete(old.id)
assert shop.products.get(old.id) is None
```

The explicit demo product number identifies the intended product. `delete()` sends
`DELETE /api/product/{id}` immediately and returns `None` on success. The mock now
returns 404 for that ID, which `get()` exposes as `None`.

## 6. Query the collection again

```python
for product in query.fetch_page().items:
    print(product.product_number, product.name, product.stock)
```

Reusing the query executes a new search. You should now see the blue and green
T-shirts, while the discontinued design is gone. A query describes a request;
it is not a cached set of results.

## Use the workflow with a real shop

First [scaffold and extend your shop's models](scaffold-and-extend.md). Use your
shop URL and `IntegrationAuth(client_id, client_secret)` from `shopware_admin`
instead of the demo token, and remove the mock `transport`. Your integration needs
permissions for each operation you execute.

Use real tax and currency IDs, valid unique product numbers, and prices consistent
with your shop's tax settings. Product creation requirements depend on the shop's
schemas and installed plugins. Currency IDs and amounts in this tutorial are demo
inputs, and the mock does not validate them. The deletion step removes a product;
choose an expendable test product in a development shop when adapting this workflow.

Continue with [scaffold and extend models](scaffold-and-extend.md), or consult the
[operation overview](../index.md#implemented-api-operations) and
[writes reference](../reference/writes.md).
