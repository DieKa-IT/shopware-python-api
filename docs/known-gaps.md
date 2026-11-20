# Known gaps and alpha status

[Documentation](index.md)

`shopware-admin` and its scaffolder are early alpha. The typed model approach is
in place, but API coverage, usability, and compatibility are incomplete. This page
records current gaps so you can judge whether the package fits your integration.
It is not a release schedule or a promise that an interface will stay unchanged.

## Incomplete endpoint coverage

The library does not provide typed interfaces for every Shopware Admin API
endpoint. Repositories cover entity search, retrieval, creation, updates, and
deletion for supported model contracts. Action endpoints and specialized workflows
do not all have dedicated helpers; for example, there is no typed sync-operation
builder. The Store API is outside the current implementation.

`shop.request()` provides a raw request escape hatch with the client's authentication,
request context, and error handling. You must supply the endpoint-specific payload
and interpret its response yourself; this does not provide the typed contract of
a repository. See [client reference](reference/client.md).

The scaffolder generates entity models from exposed schemas, not a client method
for every endpoint. An endpoint appearing in OpenAPI does not mean this package
provides a typed interface for it.

## Nested and association writes

Explicit assignments such as `shop.products.update(product_id, Product.stock.set(25))`
validate selected field values and send only those fields. Association writes are
not supported, and nested JSON updates do not fetch or preserve existing server
values. Verify server-side behavior when updating custom fields or other nested objects.

The [patch guide](how-to/patch-fields.md) documents the interface. Prepared requests
let you inspect the payload before execution, but do not resolve nested-write limitations.

## Schema and model coverage

API-aware Shopware fields can be explicitly omitted from OpenAPI. The scaffolder
cannot generate those missing declarations, so fields such as customer `vatIds`
need handwritten mappings. Dynamic custom-field names also require application
extensions. See [add missing or custom fields](how-to/add-model-fields.md) for the
Shopware PHP declaration and corresponding Python mapping.

The generator combines OpenAPI and DAL metadata; entities without a matching
exposed DAL definition are omitted. Unsupported primary-key contracts fail when
selected. Generated types describe the available metadata, which may need
refinement for your actual shop and plugins.

## No scaffolding from Shopware PHP source yet

The scaffolder cannot read Shopware's PHP source code or plugin entity definitions
directly. Its current inputs are OpenAPI and DAL schemas fetched from a running
shop or loaded from saved JSON files.

Generating models from PHP entity and field definitions is a missing feature.
Such a source could provide another way to discover API-aware fields excluded
from OpenAPI, such as customer `vatIds`. No PHP-source mode is implemented today;
those fields still require handwritten Python mappings.

## Other current limits

| Area | Current gap |
| --- | --- |
| Queries | No aggregation construction, projections, or post-filters. Collection paths use Shopware DAL semantics; there is no `.any()` quantifier. |
| Transport | Synchronous only; no asynchronous client. Flat JSON responses are supported, not JSON:API relationship envelopes. |
| Values | No dedicated money/Decimal codecs or arbitrary nested value-object codecs. Opaque `Any` values provide limited static checking. |
| Persistence | No automatic change tracking. Editing a response object does not persist it. |
| Pagination | Iteration cannot provide a snapshot of a shop changing between requests. |
| Retries | No automatic retries for transient failures or write timeouts. Token refresh handles one rejected-token retry. |

## Compatibility still needs live validation

The automated tests use mock HTTP transports and saved schema fixtures. They do
not establish compatibility with every Shopware version or plugin combination.
Validate generated models, queries, and writes against your installation. The
package is available for experimentation and evaluation and is not yet recommended
for production use.
