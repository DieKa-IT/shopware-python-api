# Explicit writes and field presence

[Documentation](../index.md)

An API response is often partial. Some fields are absent because they were not
returned or loaded. Other fields are present with JSON null. Treating both cases
as a complete object to send back can overwrite data unintentionally.

The library keeps presence separate from value. An omitted constructor argument
stays out of a create payload; an explicit `None` sends null. `default=None` permits
omission without inserting a value. It does not change a field's declared type.

On reads, a missing nullable field can return `None`, so use `is_loaded()` when you
need to distinguish absence from a returned null. Missing nonnullable fields and
unloaded collections raise `FieldNotLoadedError`. Reading an attribute never
fetches data or marks a missing value as present.

## Patches express write intent

A patch lists exactly which fields should be sent. Editing a response object does
not automatically persist it. Unknown values in `raw_data` are not silently copied
into writes. Creation uses explicitly supplied writable values and declared
creation requirements.

This keeps read state and write intent understandable, particularly when responses
are partial or contain fields that cannot be written.

Nested patches still depend on server semantics: sending one custom-field key
is not a promise that Shopware merges it with existing keys. Verify that behavior
for your installation.

## Prepared requests expose the boundary

Preparing a query or write snapshots its payload and request-context headers
without sending HTTP. You can inspect the operation before executing it. Preview
properties return copies, so changing a displayed dictionary does not alter the
request. Authentication headers are excluded from previews.

Execution is explicit, and repeated execution sends another request. Prepared
writes are not cached results, and the client does not automatically retry write
timeouts. See [patch fields](../how-to/patch-fields.md) for the workflow and
[writes reference](../reference/writes.md) for the exact contract.
