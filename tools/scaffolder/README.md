# shopware-admin-scaffold

Generate typed Python models for your Shopware 6 Admin API, ready to use with
[shopware-admin](../../README.md).

> **Early alpha — work in progress.** APIs and generated code may change without
> backward compatibility. Compatibility with individual Shopware versions and
> plugins is still being validated. Not yet recommended for production use.

The scaffolder reads your shop's schemas and creates models with typed fields,
associations, and an optional context for accessing repositories. You get
autocomplete and a Python contract without writing every mapping by hand.

Generated bases and handwritten public models live in separate files. Add custom
fields and behavior to your public subclasses; regeneration preserves those files.
The generator is a development tool. Your application imports only the runtime.

See [known gaps](../../docs/known-gaps.md) for schema coverage and compatibility
limits. Generating a model does not imply typed support for every API endpoint.

For a complete setup, follow [Connect to your shop and query products](../../docs/tutorials/connect-to-shopware.md),
including installation and creating credentials in Shopware Administration.

## Get started

Requires Python 3.12+ and uv. From `tools/scaffolder` in a checkout of this repository:

```bash
uv sync --locked
uv run shopware-admin-scaffold --help
```

For a shop requiring authentication, set `SHOPWARE_API_CLIENT_ID` and
`SHOPWARE_API_CLIENT_SECRET`, or `SHOPWARE_API_ACCESS_TOKEN`. Use one authentication
mode. With neither configured, the tool requests schemas anonymously.

Find the entities you need, then generate models into your application:

```bash
uv run shopware-admin-scaffold list --url https://shop.example --filter product
uv run shopware-admin-scaffold generate \
  --url https://shop.example \
  --output /absolute/path/to/application/src/my_shop_api --package my_shop_api \
  --entity product --entity category --context ShopContext
```

Replace the URL and output path. `--package` is the dotted Python import name of
the output directory. Add `--scaffold-related` to include direct association
targets; associations to unselected entities are otherwise omitted with a notice.
Your application needs `shopware-admin>=0.1.0a1,<0.2` as a runtime dependency.

## Use and extend the generated models

Import public classes from their modules:

```python
from my_shop_api.context import ShopContext
from my_shop_api.models.product import Product
from shopware_admin import IntegrationAuth

with ShopContext(shop_url, IntegrationAuth(client_id, client_secret)) as shop:
    for product in shop.products.where(Product.stock > 0).fetch_page().items:
        print(product.id, product.stock)
```

Supply your shop URL and integration credentials in your application.
Edit `models/product.py` to add fields or behavior, and `context.py` to add reusable
queries. Leave `_generated/` to the generator. API fields absent from schema
metadata, including dynamic custom fields, can be mapped in public subclasses:
see [add model fields](../../docs/how-to/add-model-fields.md).

## Regenerate as your shop changes

Repeat generation with the complete entity selection and `--dry-run` to preview
changes, then `--force` to replace changed generated files. Public files remain
intact. Renaming or removing existing public models requires manual reconciliation.

For repeatable generation and CI, save a schema snapshot and keep your selection
in a configuration file. Follow [scaffold and regenerate](../../docs/how-to/scaffold-models.md)
for the workflow; `--check` reports whether generated files are current without writing.

## Documentation

- [Scaffold and extend models](../../docs/tutorials/scaffold-and-extend.md): guided tutorial.
- [Scaffold and regenerate](../../docs/how-to/scaffold-models.md): configuration, snapshots, and CI.
- [CLI and configuration reference](../../docs/reference/scaffolder.md): schema sources,
  overrides, generated types, and overwrite rules.
- [Schema gaps and model ownership](../../docs/explanation/schema-gaps.md): why extensions
  belong in handwritten models.

Licensed under the [MIT License](LICENSE).
