# shopware-admin

Typed Python models, queries, and explicit writes for the Shopware 6 Admin API.

> **Early alpha — work in progress.** APIs and generated code may change without
> backward compatibility. Compatibility with individual Shopware versions and
> plugins is still being validated. Not yet recommended for production use.

See [known gaps](docs/known-gaps.md) before adopting the alpha: endpoint coverage
and support for nested writes are incomplete.

## Why this library?

Shopware integrations often repeat field names in dictionaries and query payloads.
Those strings carry a contract that your editor and type checker cannot easily see.
`shopware-admin` puts that contract into Python models: declare a field once, then
use it for typed values, query expressions, and patches.

- **Type safety:** check field values and many invalid operations before sending requests.
- **Autocomplete:** discover declared fields and associations in your editor.
- **A clearer contract:** describe types, API mappings, and write permissions explicitly.
- **Stay in Python:** use attributes and expressions instead of repeatedly assembling
  field paths and Shopware filter dictionaries.

```python
# Product and ShopContext are models and a context owned by your application.
query = shop.products.where(Product.stock > 0).order_by(Product.name.asc())
for product in query.fetch_page(size=20).items:
    print(product.name, product.stock)  # str | None, int

shop.products.update(product_id, Product.stock.set(25))
```

Generate a starting point from your shop's schemas with the separate
[scaffolder](tools/scaffolder/README.md), or write models by hand. Extend public
model subclasses for custom fields and API fields missing from the schemas.
The runtime ships no generated Shopware models and performs no schema discovery.

## Get started

Requires Python 3.12+. The distribution is `shopware-admin`; imports use `shopware_admin`.

```bash
pip install shopware-admin
```

Follow [your first query](docs/tutorials/first-query.md) for a complete example
that runs without credentials or a shop. To try the repository demo with uv:

```bash
uv sync --locked
uv run python -m examples.tshirt_collection
```

To connect to a real shop, follow [Connect to your shop and query products](docs/tutorials/connect-to-shopware.md):
install both packages, create integration credentials in Shopware Administration,
generate product models, and run your first live query.

## Documentation

- **Learn:** [Connect to your shop](docs/tutorials/connect-to-shopware.md) · [Your first query](docs/tutorials/first-query.md) ·
  [Scaffold and extend models](docs/tutorials/scaffold-and-extend.md)
- **See examples:** [Six common operations](docs/examples/common-operations.md)
- **Do:** [Query products](docs/how-to/query-products.md) ·
  [Patch fields](docs/how-to/patch-fields.md) ·
  [Add model fields](docs/how-to/add-model-fields.md) ·
  [Scaffold and regenerate](docs/how-to/scaffold-models.md)
- **Look up:** [Models](docs/reference/models.md) ·
  [Queries](docs/reference/queries.md) · [Writes](docs/reference/writes.md) ·
  [Client](docs/reference/client.md) · [Scaffolder](docs/reference/scaffolder.md)
- **Understand:** [Why typed Python](docs/explanation/why-typed-python.md) ·
  [Schema gaps and model ownership](docs/explanation/schema-gaps.md) ·
  [Explicit writes and field presence](docs/explanation/explicit-writes.md)

See the [documentation index](docs/index.md) for suggested reading paths.

The client is synchronous and targets flat JSON Admin API responses. It does not
implement the Store API, automatic change tracking, or asynchronous transport.
Typing describes your declared model; it cannot guarantee that a particular shop
exposes a field or accepts an operation.

## Contributing

See [development](docs/development.md) and [releasing](docs/releasing.md).
Licensed under the [MIT License](LICENSE).
