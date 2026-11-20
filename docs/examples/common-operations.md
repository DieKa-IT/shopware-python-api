# Six common operations

[Documentation](../index.md)

Refresh a T-shirt collection: find existing shirts, add a blue one, reduce the
green one's price, and retire an old design. These snippets assume an authenticated
`shop` context, your public `Product` model, and valid `tax_id` and `currency_id`
values from your shop.

## 1. Query T-shirts

Build a query, then execute it through Shopware's search endpoint:

```python
query = shop.products.where(Product.name.contains("T-shirt"))
for product in query.fetch_page(size=20).items:
    print(product.product_number, product.name)
```

## 2. Create a blue T-shirt

Supply the intended creation values; `create()` returns the new ID after success:

```python
blue = Product(
    name="Blue T-shirt",
    product_number="DEMO-TSHIRT-BLUE",
    stock=20,
    tax_id=tax_id,
    price=[{"currencyId": currency_id, "gross": 29.75, "net": 25.00, "linked": True}],
)
blue_id = shop.products.create(blue)
```

## 3. Get it by ID

When you know the ID, retrieve the product directly rather than searching:

```python
created = shop.products.get(blue_id)
if created is not None:
    print(created.name, created.stock)
```

## 4. Patch the green T-shirt's price

Find exactly one product by its unique product number, then update only its price:

```python
green = shop.products.where(Product.product_number == "DEMO-TSHIRT-GREEN").one()
shop.products.update(
    green.id,
    Product.price.set([{"currencyId": currency_id, "gross": 17.85, "net": 15.00, "linked": True}]),
)
```

## 5. Delete the discontinued design

Select the intended demo product explicitly; `delete()` sends the request immediately:

```python
old = shop.products.where(Product.product_number == "DEMO-TSHIRT-OLD").one()
shop.products.delete(old.id)
```

## 6. Query the updated collection

Executing the query again reads current results, including the blue shirt and
excluding the deleted one:

```python
for product in query.fetch_page(size=20).items:
    print(product.product_number, product.name)
```

## Run the complete example

The [runnable demo](../../examples/tshirt_collection.py) includes models, a context,
and an in-memory shop with the green and discontinued shirts already seeded.
Run it from the repository root with Python 3.12+ and uv:

```bash
uv sync --locked
uv run python -m examples.tshirt_collection
```

It makes no live requests and resets on every run. Its mock transport implements
only the behavior used by this example, not all Shopware validation rules.

## Details for your own shop

These are standalone products; color variants require additional modeling.
Creation requirements vary with your shop and plugins. The amounts above assume
19% VAT and explicitly supply both gross and net. Prices are currency-specific
lists: verify how to preserve other currency entries before patching a real
product. The client provides no client-side merge guarantee for nested writes.
Use an expendable product in a development shop for the deletion example.

- [Scaffold your models](../tutorials/scaffold-and-extend.md)
- [Query and load associations](../how-to/query-products.md)
- [Patch fields and preview requests](../how-to/patch-fields.md)
- [Creation and write contracts](../reference/writes.md)
- [Known gaps and nested-write limitations](../known-gaps.md)
