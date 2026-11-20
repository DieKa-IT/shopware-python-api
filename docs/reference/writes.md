# Writes and prepared requests

[Documentation](../index.md)

Examples assume an authenticated `shop` context with a `products` entity set;
`products` is shorthand for `shop.products`. See [models and contexts](models.md).

```python
products.update(product_id, Product.name.set("Updated"), Product.parent_id.set(None))
products.delete(product_id)

request = products.prepare_update(
    product_id, Product.name.set("Updated"), Product.parent_id.set(None)
)
print(request.method, request.path, request.json, request.headers)
request.execute()
```

`Model.field.set(value)` returns an immutable `Patch[Model]` and validates the
value without sending HTTP. Field expressions carry both model and value types:
`Product.stock` is `FieldExpression[Product, int]`, so `.set(12)` returns
`Patch[Product]`. `Patch` is invariant in its model type.

`update(entity_id, *changes)` sends one HTTP PATCH request immediately;
`prepare_update(entity_id, *changes)` returns a `PreparedRequest[None]`. Both require
at least one selected field and reject patches whose model is not the repository's
exact model, including base classes and other subclasses for the same entity.
Use the public model to access inherited fields, such as `Product.stock`.
Association traversal fields cannot be assigned.

Assignments can be collected and unpacked with `*changes`. When a field is assigned
more than once, the last assignment wins. Nested paths are assembled into one
payload, preserving sibling keys selected by other assignments in that request.
Patch inputs remain unchanged, and mutable input values are snapshotted when selected.

The existing `products.patch().set(Product.stock, 12)` builder remains supported;
its patches can also be passed to `update()` and `prepare_update()`.

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
