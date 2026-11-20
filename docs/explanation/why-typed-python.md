# Why typed Python?

[Documentation](../index.md)

A Shopware integration carries a contract: field names, value types, associations,
and allowed operations. In raw JSON requests, much of that contract lives in
strings and dictionary shapes. A misspelled field path can look like valid Python
until the request reaches the server.

This library makes the application model an explicit Python description of that
contract. The same field declaration describes an instance value, a query operand,
and a patch target:

```python
Product.stock > 0
product.stock
shop.products.update(product_id, Product.stock.set(25))
```

## Type safety and autocomplete

A declared `Field[int]` exposes an integer on instances and a typed expression on
the model class. Editors can complete fields and association paths. Type checkers
can catch unknown attributes and many invalid values before execution. Runtime
validation also checks values, including rejecting numeric strings for integers.

This is not proof that a request will succeed. Your shop's permissions, plugins,
version, data, and field capabilities still determine server behavior. Opaque
`Any` fields provide less static checking. Python equality is permissive;
`.eq(value)` provides stricter static operand checking than `==`.

## Keep application code in one language

Python attributes express paths such as `Product.manufacturer.name`, and Python
operators express supported comparisons. Callers do not need to repeatedly write
Shopware's filter names or duplicate wire-field strings. Renaming and navigating
model attributes becomes part of normal Python development.

The API still has conventions. Wire names belong in mapping declarations, and
Python requires `&`, `|`, and `~` for composable predicates rather than `and`, `or`,
and `not`. The query reference explains these boundaries explicitly.

## A contract your application owns

Schema generation reduces repetitive declarations. Public subclasses let you
refine that starting point for the shop you actually integrate with. The runtime
uses those declarations without fetching schemas at startup.

This makes schema gaps visible and correctable in code, while preserving editor
support for handwritten extensions. Read [schema gaps and model ownership](schema-gaps.md)
for the generated-base boundary and [explicit writes](explicit-writes.md) for why
updates select fields deliberately.
