# Queries and execution

[Documentation](../index.md)

The examples use the `Product`, `Category`, and `ShopContext` declarations from
[models and contexts](models.md). Connection values such as `shop_url` and
`client_id` are supplied by your application.

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
