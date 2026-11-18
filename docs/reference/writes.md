# Writes and prepared requests

[Documentation](../index.md)

**Alpha interface:** the current patch API is cumbersome and needs major reworking.
The examples describe its present behavior; patch construction may change incompatibly.
See [known gaps](../known-gaps.md#patch-api-needs-major-reworking).

Examples assume an authenticated `shop` context with a `products` entity set;
`products` is shorthand for `shop.products`. See [models and contexts](models.md).

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
