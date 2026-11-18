# Connect to your shop and query products

[Documentation](../index.md)

Start with an empty Python project, create Shopware integration credentials,
scaffold a product model, and query real products. This tutorial reads schemas and
products; it does not create, update, or delete shop records.

You need Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/),
a reachable Shopware 6 shop, and access to manage integrations in its
Administration. Use a development shop to evaluate the alpha; see [known gaps](../known-gaps.md).
Commands below use a POSIX shell such as Bash or Zsh.

## 1. Install the library and scaffolder

Create an application project and install both released packages from PyPI:

```bash
uv init --python 3.12 shopware-demo
cd shopware-demo
uv add --prerelease allow shopware-admin
uv add --dev --prerelease allow shopware-admin-scaffold
uv run shopware-admin-scaffold --version
```

The distribution `shopware-admin` supplies the runtime imported as `shopware_admin`.
`shopware-admin-scaffold` supplies the generator command. The generator is a
development dependency; generated code imports only the runtime.

`--prerelease allow` permits the current alpha releases. Keep running all remaining
commands from `shopware-demo`. Generated models will belong to your application.

## 2. Create a Shopware integration

Open your shop's Administration, usually `https://your-shop.example/admin`, and
sign in with an account allowed to manage integrations.

1. Open **Settings → System → Integrations**. Depending on the Shopware version,
   the settings page may show **Integrations** without a separate System category.
2. Select **Add integration** and give it a name such as `Python product reader`.
3. Assign a role with product read permission. The integration also needs access
   to the schema endpoints used below. For an initial test on a development shop,
   the **Administrator** option can provide that access; it grants broad permissions.
   For a restricted integration, have your shop administrator assign the required role.
4. Copy the **Access key ID** and **Secret access key** before closing the dialog.
   The secret will not be shown again after saving.
5. Select **Save integration**. The credentials become active after saving.

These are integration credentials for the Admin API, not a sales-channel access
key or your Administration username and password. The client exchanges them for
an OAuth access token automatically; you do not need to obtain a token manually.

## 3. Set the connection and credentials

Set these variables in the same terminal where you will run the generator and Python:

```bash
export SHOPWARE_URL='https://your-shop.example'
export SHOPWARE_API_CLIENT_ID='your-access-key-id'
export SHOPWARE_API_CLIENT_SECRET='your-secret-access-key'
unset SHOPWARE_API_ACCESS_TOKEN
```

Replace the example values with your shop's values. `SHOPWARE_URL` is the shop's
base URL, without `/admin` or `/api`.

| Shopware Administration label | Environment variable |
| --- | --- |
| Access key ID | `SHOPWARE_API_CLIENT_ID` |
| Secret access key | `SHOPWARE_API_CLIENT_SECRET` |

The scaffolder reads the credential variables automatically. The Python code below
reads the same values explicitly. `SHOPWARE_URL` is an application convention used
in this tutorial; pass it to the scaffolder with `--url`.

Use either integration credentials or `SHOPWARE_API_ACCESS_TOKEN`, not both.
These exports apply to the current shell; repeat them in a new terminal. Keep the
secret out of committed files. Neither package automatically loads a `.env` file.

## 4. Check schema access and scaffold products

First check that the generator can read your shop's schemas:

```bash
uv run shopware-admin-scaffold list --url "$SHOPWARE_URL" --filter product
```

The output should include the `product` entity. The command reads the shop's
OpenAPI and DAL schemas; it does not search the product records themselves.

Generate a product model and a context into a new application package:

```bash
uv run shopware-admin-scaffold generate \
  --url "$SHOPWARE_URL" \
  --output ./my_shop_api --package my_shop_api \
  --entity product --context ShopContext
```

The files you will use are:

```text
shopware-demo/
  my_shop_api/
    models/product.py             # Public Product class; add your extensions here
    context.py                    # Public ShopContext class
    _generated/model_bases.py     # Generated product field declarations
    _generated/context_base.py    # Generated products entity set
```

This generates Python code directly from live schemas. A `snapshot` step is
optional; it saves schema JSON for later offline generation rather than creating
models. See [scaffold and regenerate](../how-to/scaffold-models.md) when you want
repeatable schema inputs or configuration for subsequent runs.

Associations to entities you did not select are omitted with a notice. That is
expected here: the first query only uses product fields. Keep handwritten changes
in public files rather than `_generated/`.

## 5. Query your products

Save this as `query_products.py` in `shopware-demo`, beside `my_shop_api`:

```python
import os

from my_shop_api.context import ShopContext
from my_shop_api.models.product import Product
from shopware_admin import IntegrationAuth

with ShopContext(
    os.environ["SHOPWARE_URL"],
    IntegrationAuth(
        os.environ["SHOPWARE_API_CLIENT_ID"],
        os.environ["SHOPWARE_API_CLIENT_SECRET"],
    ),
) as shop:
    query = shop.products.where(Product.stock > 0).order_by(Product.id.asc())
    result = query.fetch_page(size=10)
    print(f"Products on this page: {len(result.items)}")
    for product in result.items:
        print(product.id, product.name, product.stock)
```

Run it in the terminal where you exported the credentials:

```bash
uv run python query_products.py
```

You should see up to ten products with stock greater than zero. An empty page is
valid if no products match. To inspect products without that filter, replace the
query line with `query = shop.products.search().order_by(Product.id.asc())`.

Building the query performs no HTTP request. `fetch_page()` executes it through
`POST /api/search/product`. The returned values use your generated `Product` type;
your editor can complete its fields.

## If a step fails

| Symptom | Check |
| --- | --- |
| Schema loading returns HTTP 401 | The integration was saved, both keys were copied correctly, and the URL points to the same shop. |
| Schema loading or product queries return HTTP 403 | The integration's role permits the requested operation. Schema access and product read access are separate checks. |
| Connection, TLS, or unexpected HTTP errors | The shop base URL is reachable from your Python environment and has a valid certificate; do not use the Administration URL. |
| `ModuleNotFoundError: my_shop_api` | Generation succeeded and the script is beside the generated package; run from `shopware-demo`. |
| A field is missing from the generated model | Check the generated declarations and [add fields omitted from OpenAPI](../how-to/add-model-fields.md) if needed. |

Continue with [six common operations](../examples/common-operations.md) or
[scaffold and extend models](scaffold-and-extend.md). The latter demonstrates
mapping customer VAT IDs when Shopware exposes them through the API but excludes
them from OpenAPI.
