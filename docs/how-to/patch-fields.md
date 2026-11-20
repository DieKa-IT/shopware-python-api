# Patch selected fields

[Documentation](../index.md)

Use a patch when updating an existing entity. Assume `shop` is an authenticated
context, `Product` is your public model, and `product_id` identifies the product.

## Select the values to send

```python
shop.products.update(
    product_id,
    Product.stock.set(25),
    Product.parent_id.set(None),
)
```

The payload contains only `stock` and `parentId`. Explicit `None` becomes JSON
null; omitted fields are absent. Values are checked against the model declaration.
Primary IDs and read-only fields cannot be patched. `update()` immediately sends
all assignments in one HTTP PATCH request; no entity needs to be loaded first.

## Preview an update

Use the same assignments with `prepare_update()` to inspect a request before sending it:

```python
request = shop.products.prepare_update(
    product_id,
    Product.stock.set(25),
    Product.parent_id.set(None),
)
print(request.method, request.path, request.json)
request.execute()
```

Preparing a request does no network I/O. Executing it again sends it again.

## Collect assignments

```python
changes = [Product.stock.set(25), Product.name.set("Updated")]
shop.products.update(product_id, *changes)
```

Each assignment is a `Patch[Product]`. Type checkers reject patches for another
model, and the runtime checks model ownership before sending HTTP. Access inherited
fields through the public model (`Product.stock`); newly declared fields work the
same way without regenerating an update signature.

## Patch a custom field

With the mapping from [add model fields](add-model-fields.md):

```python
patch = Product.erp_reference.set("ERP-4711")
print(shop.products.prepare_update(product_id, patch).json)
# {"customFields": {"erp_reference": "ERP-4711"}}
```

The runtime sends that nested object. It does not fetch or preserve sibling keys,
and it does not promise a server-side merge. Verify your shop's write behavior;
when replacement is required, supply the complete intended object through an
appropriate writable object mapping.

See [writes reference](../reference/writes.md) for creation and prepared-request
behavior, and [explicit writes](../explanation/explicit-writes.md) for the reasoning.
