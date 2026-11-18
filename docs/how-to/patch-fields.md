# Patch selected fields

[Documentation](../index.md)

Use a patch when updating an existing entity. Assume `shop` is an authenticated
context, `Product` is your public model, and `product_id` identifies the product.

## Select the values to send

```python
patch = (
    shop.products.patch()
    .set(Product.stock, 25)
    .set(Product.parent_id, None)
)
request = shop.products.prepare_update(product_id, patch)
print(request.method, request.path, request.json)
```

The payload contains only `stock` and `parentId`. Explicit `None` becomes JSON
null; omitted fields are absent. Values are checked against the model declaration.
Primary IDs and read-only fields cannot be patched.

## Execute the update

After inspecting the request, send it:

```python
request.execute()
```

If you do not need a preview, use `shop.products.update(product_id, patch)`.
Preparing a request does no network I/O. Executing it again sends it again.

## Patch a custom field

With the mapping from [add model fields](add-model-fields.md):

```python
patch = shop.products.patch().set(Product.erp_reference, "ERP-4711")
print(shop.products.prepare_update(product_id, patch).json)
# {"customFields": {"erp_reference": "ERP-4711"}}
```

The runtime sends that nested object. It does not fetch or preserve sibling keys,
and it does not promise a server-side merge. Verify your shop's write behavior;
when replacement is required, supply the complete intended object through an
appropriate writable object mapping.

See [writes reference](../reference/writes.md) for creation and prepared-request
behavior, and [explicit writes](../explanation/explicit-writes.md) for the reasoning.
