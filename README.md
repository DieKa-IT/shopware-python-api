# shopware-admin-python

> **Early alpha — work in progress.** Available for experimentation and evaluation.
> APIs and generated code may change without backward compatibility. Compatibility
> with individual Shopware versions and plugins is still being validated.
> Not yet recommended for production use.

Licensed under the [MIT License](LICENSE).

A first version of a typed, synchronous Shopware 6 Admin API client. Query fields
and entity values share one descriptor declaration:

```python
Product.stock > 0  # Predicate; compiled to a Shopware range filter
product.stock  # int
```

The runtime works with handwritten models and defines the model contract for a
future scaffolder. It does not discover schemas or generate source code.

The separate [scaffolder CLI](tools/scaffolder/README.md) generates model bases,
public extension shells, and optional contexts from live or saved Shopware schemas.
It has its own package and lockfile under `tools/scaffolder`; generated models live
in consuming applications. See the [architecture proposal](docs/scaffolding-proposal.md)
for the design background.

## Try the interface

Requires Python 3.12+ and uv.

```bash
uv sync --locked
uv run python -m examples.demo
```

The demo uses HTTPX MockTransport. It prints a prepared Shopware search, hydrates
typed products, and previews a patch. It requires no credentials or running shop.

Use the library from another uv project during development:

```bash
uv add --editable /absolute/path/to/shopware-admin-python
```

## Models

```python
from shopware_admin import (
    Entity,
    Field,
    ToMany,
    ToOne,
    api_field,
    to_many,
    to_one,
)


class Manufacturer(Entity):
    __entity__ = "product_manufacturer"
    __route__ = "product-manufacturer"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)


class Category(Entity):
    __entity__ = "category"
    __route__ = "category"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)
    active: Field[bool] = api_field("active", default=None)


class ProductBase(Entity):
    __entity__ = "product"
    __route__ = "product"

    id: Field[str] = api_field("id", default=None)
    name: Field[str | None] = api_field("name", default=None)
    stock: Field[int] = api_field("stock", default=None, required_on_create=True)
    active: Field[bool | None] = api_field("active", default=None)
    parent_id: Field[str | None] = api_field("parentId", default=None)
    manufacturer: ToOne[Manufacturer] = to_one("manufacturer")
    categories: ToMany[Category] = to_many("categories")


class Product(ProductBase):
    erp_reference: Field[str | None] = api_field(
        json_path=("customFields", "erp_reference"),
        criteria_path="customFields.erp_reference",
        default=None,
    )
```

These are illustrative declarations, not a complete or version-independent
Shopware product schema. Define model classes at module scope so Python can
resolve annotations, including forward references. Field types are resolved
from annotations when first used.

- `__entity__` identifies the DAL entity; `__route__` is its exact API route.
- `Field[T]` gives `T` on instances and `FieldExpression[T]` on classes.
- `ToOne[T]` gives `T | None`; `ToMany[T]` gives `list[T]` on instances.
- On classes, associations reuse the related entity type for typed dotted queries.
  `Product.manufacturer.name` is a field expression; on an instance,
  `product.manufacturer.name` is the returned value.
- `default=None` permits omission from a constructor without making `T` nullable.
  It does not insert or serialize a value when the argument is omitted. This
  parameter controls constructor optionality; concrete value defaults are assigned explicitly.
- A field without an explicit default is required by the typed constructor.
- `required_on_create=True` separately checks required write values at creation.
- `writable=False` allows hydration but rejects assignment and patches.
- Associations are read-only and excluded from constructors by default.

Keep generated base classes and handwritten public subclasses in separate files.
Declare the public models in a context (below), or register them with a plain
client, so associations referring to a base class hydrate into the public subclass.
Duplicate JSON mappings and incompatible
registrations fail explicitly. An added field must already be exposed by Shopware.

Supported values are strict Python scalars, optional unions, typed lists/dicts,
`datetime`, and opaque `Any` values. Numeric strings are not coerced to integers,
and booleans are not accepted as integers. Dedicated money/Decimal codecs and
arbitrary nested value-object codecs are follow-up work.

## Typed contexts

Declare named entity sets once, then access repositories directly:

```python
from shopware_admin import Context, Query, entity_set


class ShopContextBase(Context):
    products = entity_set(Product)
    categories = entity_set(Category)
    manufacturers = entity_set(Manufacturer)


class ShopContext(ShopContextBase):
    def available_products(self) -> Query[Product]:
        return self.products.where(Product.stock > 0)
```

`shop.products` is a `Repository[Product]`, with typed query results, patches,
and autocomplete. The context registers every declared model at construction,
including inherited sets, so related entities hydrate into public subclasses
even before their repositories are accessed. No `models=[Product]` argument is
needed. Constructing a context, accessing an entity set, and building a query
perform no HTTP requests. Entity set properties are read-only.

For a future scaffolder, keep the generated context base and handwritten context
subclass in separate files. The base imports the **public model classes**, such as
`Product`, rather than `ProductBase`. This preserves the extended model types
without overriding inherited repository properties. The handwritten context can
add methods and entity sets. See `examples.context_base` and `examples.context`;
these are handwritten illustrations, not generated runtime models.

`Context` accepts the same connection, authentication, timeout, transport, and
request-context arguments as `Client`. Its optional `models=` argument can
register additional association models without declaring named sets. A plain
`Client` and `client.set(Product)` remain available for existing code.

## Queries

```python
from shopware_admin import CountMode, IntegrationAuth

with ShopContext(shop_url, IntegrationAuth(client_id, client_secret)) as shop:
    query = (
        shop.products.where(Product.name.contains("ring"), Product.stock > 0)
        .where(Product.manufacturer.name == "Example")
        .order_by(Product.name.asc(), Product.id.asc())
        .load(Product.manufacturer)
    )
    result = query.fetch_page(page=1, size=100, count=CountMode.EXACT)
    for product in result.items:
        print(product.name, product.stock, product.erp_reference)
```

The following snippets use `products` as shorthand for `shop.products`.

Queries and criteria are immutable. Multiple `where()` arguments and successive
`where()` calls combine with AND. `filter()` is an alias.

```python
products.where((Product.name == "blub") & (Product.stock > 0))
products.where((Product.stock > 0) | (Product.active == True))
products.where(~Product.parent_id.is_null())
products.where(Product.id.in_([id_a, id_b]))
```

Use parentheses with `&` and `|`. Python `and`, `or`, `not`, and chained
comparisons attempt boolean evaluation and are rejected. `field is None` produces
a Python boolean, which `where()` rejects; use `is_null()` or `== None`.

| Operation | Shopware criteria |
| --- | --- |
| `==`, `.eq(value)` | `equals` |
| `!=`, `~predicate` | `not` |
| `.in_(values)` | `equalsAny` |
| `<`, `<=`, `>`, `>=` | Numeric/datetime `range` |
| `.contains()`, `.startswith()`, `.endswith()` | `contains`, `prefix`, `suffix` |
| `.asc()`, `.desc()` | Sorting; optional `natural=True` |

`==` follows Python's permissive equality protocol and validates the operand at
runtime. `.eq(value)` additionally gives strict static operand checking.
Field-to-field comparisons and empty `in_()` values are rejected.

Association queries use normal dotted attributes:

```python
products.where(Product.manufacturer.name == "Example")
products.where(Product.categories.name == "Seals")
```

The complete models in `examples.models` also support nested paths:

```python
products.where(Product.manufacturer.media.url.contains("example"))
products.where(Product.categories.parent.name == "Seals")
```

Each path retains the queried root entity. On a product query,
`Product.manufacturer.name` compiles to the field `manufacturer.name` in the
root filter: it selects products whose manufacturer's name matches. Filtering
does not implicitly configure association loading; add `.load()` for the related
data you want returned.

Declare each entity once. Association access on a class creates an internal view
of the related entity class carrying the query path. Its existing descriptors
supply autocomplete, field types, JSON aliases, and nested associations. No
additional field classes or annotations are needed, including for handwritten
extensions. Unknown members fail both static checking and runtime lookup.
Instance access continues to return the declared entity or collection.

Collection paths have Shopware DAL semantics; this version does not offer
SQL-style joins or an `.any()` quantifier.

Load collection associations with their own criteria:

```python
from shopware_admin import Criteria

query = products.where(Product.stock > 0).load(
    Product.categories,
    criteria=Criteria(Category).where(Category.active == True).limit(10),
)
```

Root filtering selects products. Nested criteria restrict the categories loaded
for each result. Filtering by an association does not automatically load it.

## Execution and field presence

```python
query.fetch_page(page=1, size=100)  # SearchResult[Product]
query.first()  # Product | None; requests one row
query.one()  # Product; requests two to check cardinality
query.ids(page=1, size=100)  # list[str]; search-ids, without associations
query.iter(page_size=500)  # Iterator[Product]; explicitly traverses pages
products.get(product_id)  # Product | None; only HTTP 404 means missing
```

`SearchResult` includes items, count metadata, and aggregations returned by the
server. Default `CountMode.NONE` exposes `total=None`. `EXACT` requests an exact
total; `NEXT_PAGES` preserves the approximate count without claiming it is exact.
Aggregation construction, projections, and post-filters are not implemented yet.

`iter()` appends an ID tie-breaker when necessary. It cannot provide a snapshot
of a shop changing during pagination. Use `page_size` rather than `limit()` with
`iter()`; query `limit()` otherwise sets the per-request root limit.

A loaded JSON null becomes `None`. An omitted nullable scalar or to-one
association also reads as `None`; an omitted nonnullable field or to-many
association raises `FieldNotLoadedError`, preserving its declared type. An
unloaded collection differs from an empty loaded collection. Shopware's JSON null
for an unloaded to-many association also remains unloaded; an empty array means
the collection was loaded without members.
`product.is_loaded(Product.manufacturer)` checks whether the field was supplied,
returned, or subsequently assigned. It uses the keys of the entity's internal
value dictionary; no separate presence dictionary is needed. Reading omitted
nullable attributes does not insert values or change a create payload.
Reading attributes never triggers HTTP requests. `product.raw_data` returns a
copy of the original response, including unknown fields; unknown fields are not
automatically included in writes.

## Explicit writes and previews

```python
patch = products.patch().set(Product.name, "Updated").set(Product.parent_id, None)
products.update(product_id, patch)
products.delete(product_id)

request = products.prepare_update(product_id, patch)
print(request.method, request.path, request.json, request.headers)
request.execute()
```

Only selected patch fields are sent; explicit `None` sends JSON null. Patches
cannot change the primary ID or write read-only fields. A nested JSON patch such
as `customFields.erp_reference` sends only that nested object: the runtime does
not promise a merge or preserve sibling keys. Confirm the shop's write semantics
and supply the complete intended JSON object when replacement is required.

`products.create(fresh_entity)` serializes only explicitly supplied writable
fields and validates declared creation requirements. It preserves an explicit ID
or generates a UUID hex ID locally, returns it after success, and fills the
entity's mapped ID. See `examples.models.Product` for an illustrative create model
including product number, stock, tax, and price. Create fresh instances with the
intended write values; do not use response objects as implicit update payloads.

```python
Product().to_payload()  # {}
Product(name=None).to_payload()  # {"name": None}
```

The constructor records which keyword arguments were actually supplied. An
omitted field is left out of the create payload so Shopware can apply its default;
explicit `None` sends JSON null. Patches continue to use the fields selected by
`.set()`, and queries continue to send their criteria independently of entity values.

`query.prepare()`, `products.prepare_get()`, `prepare_create()`, and
`prepare_update()` perform no HTTP requests. They snapshot payloads and context
headers. Preview properties return copies; editing them does not change what is
sent. A prepared create's generated ID is fixed before execution. Calling
`execute()` again sends the request again; prepared writes are not cached results.

## Transport

The client reuses an HTTPX connection pool, authenticates with integration
credentials, refreshes expiring tokens, and retries one rejected-token request
after a 401. It does not automatically retry transient failures or write timeouts.
`AccessToken(token)` supports externally managed tokens without refresh.

```python
from shopware_admin import RequestContext

localized = shop.with_context(RequestContext(language_id=language_id, inheritance=True))
localized.products.where(Product.stock > 0).fetch_page()

shop.request("POST", "/api/_action/sync", payload)  # Raw action escape hatch
```

`request()` also accepts query parameters and raw binary bodies. Keep query
parameters separate from the relative `/api/` path:

```python
shop.request(
    "POST",
    f"/api/_action/media/{media_id}/upload",
    params={"extension": "svg", "fileName": "o-ring"},
    content=svg_bytes,
    content_type="image/svg+xml",
)
```

Use either the existing JSON `payload` argument or `content` bytes. `content_type`
requires binary content. Responses remain decoded JSON, or `None` for an empty
successful response such as HTTP 204. Authentication, request context, structured
errors, and the single refresh after a 401 apply to both body formats. Binary
requests are replayed with identical bytes after a refresh; write timeouts are
not automatically retried.

`with_context()` preserves the concrete context class, its named entity sets, and
custom methods. Views are shallow copies: they share the connection, authentication,
model registry, and any custom mutable attributes. Their request settings are
independent. Entity sets bind to the accessing view, so localized requests use its
headers. Closing a view does not close the owner's connection; close the owning
client after all views finish. Supported headers are language, version, and inheritance.
API errors retain HTTP status and structured error entries, including source
pointers; previews exclude authentication headers and credential representations.
The client currently supports flat `application/json` Admin API responses and
conventional UUID primary IDs. It does not decode JSON:API relationship envelopes
or implement the Store API, asynchronous transport, automatic tracking, or sync
operation builders.

## Development

```bash
uv sync --locked
uv run pytest
uv run mypy
uv run pyright
uv run ruff check .
uv run ruff format --check .
uv build
```

Tests use HTTPX MockTransport, not a live shop. `tests/typing_contract.py` checks
typed constructors, values, nested field traversal, repositories, query results,
and invalid inputs with both mypy and Pyright. Live integration compatibility
with your particular Shopware version and installed plugins remains to be tested.
