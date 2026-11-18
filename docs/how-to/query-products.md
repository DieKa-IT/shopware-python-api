# Query products and load associations

[Documentation](../index.md)

Assume `shop` is an authenticated context and `Product` and `Category` are your
public models. The examples use fields declared in the repository's
[example models](../../examples/models.py).

## Filter and sort

```python
query = shop.products.where(Product.stock > 0, Product.name.contains("ring")).order_by(
    Product.name.asc(), Product.id.asc()
)
result = query.fetch_page(page=1, size=100)
```

Multiple predicates and successive `where()` calls combine with AND. For OR or
negation, use `|` and `~` with parentheses:

```python
query = shop.products.where((Product.stock > 0) | (Product.active == True))
query = query.where(~Product.parent_id.is_null())
```

Python `and`, `or`, `not`, and chained comparisons do not build query expressions.
Use `is_null()` rather than `is None`. Use `.eq(value)` when you want strict static
operand checking for equality; Python's `==` protocol is more permissive.

## Filter through an association and return its data

```python
query = shop.products.where(Product.manufacturer.name == "Example").load(Product.manufacturer)
```

The filter selects products. `.load()` requests the related manufacturer data.
Filtering alone does not load an association.

To restrict which collection members are returned, give the load its own criteria:

```python
from shopware_admin import Criteria

query = shop.products.where(Product.stock > 0).load(
    Product.categories,
    criteria=Criteria(Category).where(Category.active == True).limit(10),
)
```

## Choose how to consume results

```python
from shopware_admin import CountMode

page = query.fetch_page(page=1, size=100, count=CountMode.EXACT)
print(page.total)

for product in query.iter(page_size=500):
    print(product.id)
```

Use `fetch_page()` for a specific page and `iter()` to traverse pages. Iteration
adds an ID tie-breaker as needed, but does not give a snapshot of a changing shop.
Avoid query `limit()` with `iter()`; use `page_size`.

For a single result, use `first()` (possibly `None`) or `one()` (requires exactly
one). For IDs only, use `ids()`. See [query reference](../reference/queries.md)
for count modes, field presence, and supported operators.
