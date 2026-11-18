# Your first query

[Documentation](../index.md)

Find T-shirts and read typed results. With your application's `Product` model and
`ShopContext`, the query is:

```python
query = shop.products.where(Product.name.contains("T-shirt"))
for product in query.fetch_page(size=20).items:
    print(product.name, product.stock)
```

Building `query` sends nothing. `fetch_page()` executes it through Shopware's search
endpoint and returns typed products. `Product.name` describes a field in the query;
`product.name` reads a value on a returned product.

## Run your first query

For a first run without a shop or credentials, use Python 3.12+ and uv in a checkout
of this repository:

```bash
uv sync --locked
```

Save the following as `first_query.py` in the repository root. The example imports
existing models so you can focus on using them.

```python
import httpx

from examples.context import ShopContext
from examples.models import Product
from shopware_admin import AccessToken


def respond(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": [{"id": "1" * 32, "name": "Green T-shirt", "stock": 12}],
        },
    )


with ShopContext(
    "https://shop.example",
    AccessToken("demo"),
    transport=httpx.MockTransport(respond),
) as shop:
    query = shop.products.where(Product.name.contains("T-shirt"))
    for product in query.fetch_page(size=20).items:
        print(product.name, product.stock)
```

Run it:

```bash
uv run python first_query.py
```

You should see `Green T-shirt 12`. The mock returns a fixed response; it lets you
execute the query and inspect typed results without implementing a server.

## Change the query

Add sorting before executing:

```python
query = shop.products.where(Product.name.contains("T-shirt")).order_by(Product.name.asc())
print(query.prepare(size=20).json)
```

Place this inside the `with` block. The preview now includes the filter and sort;
preparing it makes no HTTP request. The fixed mock response stays the same.

Continue with [six common operations](../examples/common-operations.md) for a quick
view of creating, retrieving, updating, and deleting products. To use your own
shop, follow [scaffold and extend models](scaffold-and-extend.md), then construct
your context with its URL and `IntegrationAuth(client_id, client_secret)` from
`shopware_admin` instead of the mock transport and demo token.
