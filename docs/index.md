# Documentation

`shopware-admin` expresses Shopware API contracts through Python models. Use the
separate scaffolder to generate an initial model, then refine it for your shop.

Read [known gaps and alpha status](known-gaps.md) for incomplete endpoint coverage,
nested-write limitations, and compatibility limits.

These docs follow [Diátaxis](https://diataxis.fr/): tutorials teach through a guided
experience, how-to guides solve tasks, reference describes behavior, and explanation
covers the reasons behind the design.

## Implemented API operations

Repositories provide the following operations for supported entity models.
Here `products` means `shop.products`; routes use the model's declared API route.

| Operation | Python interface | HTTP endpoint | Documentation |
| --- | --- | --- | --- |
| Search entities | `products.where(...).fetch_page()` | `POST /api/search/{route}` | [Query guide](how-to/query-products.md) |
| Search IDs only | `products.search().ids()` | `POST /api/search-ids/{route}` | [Query reference](reference/queries.md) |
| Read one entity by ID | `products.get(entity_id)` | `GET /api/{route}/{id}` | [Query reference](reference/queries.md) |
| Create an entity | `products.create(entity)` | `POST /api/{route}` | [Writes reference](reference/writes.md) |
| Update selected fields | `products.update(entity_id, patch)` | `PATCH /api/{route}/{id}` | [Patch guide](how-to/patch-fields.md) |
| Delete an entity | `products.delete(entity_id)` | `DELETE /api/{route}/{id}` | [Writes reference](reference/writes.md) |
| Call other endpoints directly | `shop.request(method, path, ...)` | Caller-supplied `/api/` path | [Client reference](reference/client.md) |

`get()` returns a typed entity or `None` for HTTP 404. `create()` returns the new
ID after success. `update()` and `delete()` return `None` after success.
`prepare_get()`, `prepare_create()`, and `prepare_update()` allow previews before
execution; there is currently no `prepare_delete()` helper.

Raw requests share authentication and transport handling but do not provide typed
endpoint-specific payloads or results. Specialized action helpers, including a
typed sync-operation builder, are still missing. See [known gaps](known-gaps.md).

## Tutorials — learn by doing

Start here if you are new to the library.

- [Connect to your shop and query products](tutorials/connect-to-shopware.md): install
  the packages, create Shopware integration credentials, scaffold products, and query them.
- [Your first query](tutorials/first-query.md): run a small query and read typed
  results without a live shop.
- [Scaffold and extend models](tutorials/scaffold-and-extend.md): generate models
  from a shop and add a VAT ID mapping missing from OpenAPI.

## Examples — see the interface

[Six common operations](examples/common-operations.md) shows query, create, get,
patch, delete, and query again through a T-shirt collection example. A runnable
mock-shop demo is linked separately so you can read the library code first.

## How-to guides — complete a task

These guides assume you have a model and can construct a context.

- [Query products and load associations](how-to/query-products.md)
- [Patch selected fields](how-to/patch-fields.md)
- [Add missing or custom fields to a model](how-to/add-model-fields.md)
- [Scaffold and regenerate models](how-to/scaffold-models.md)

## Reference — look up the contract

- [Models and contexts](reference/models.md)
- [Queries, pagination, execution, and field presence](reference/queries.md)
- [Writes and prepared requests](reference/writes.md)
- [Client, authentication, request context, and transport](reference/client.md)
- [Scaffolder CLI and configuration](reference/scaffolder.md)

## Explanation — understand the design

- [Why typed Python?](explanation/why-typed-python.md)
- [Schema gaps and model ownership](explanation/schema-gaps.md)
- [Explicit writes and field presence](explanation/explicit-writes.md)

## Project maintenance

[Development](development.md) · [Releasing](releasing.md) ·
[Scaffolder architecture proposal](scaffolding-proposal.md)

The architecture proposal records design background; use the scaffolder reference
for its current behavior.
