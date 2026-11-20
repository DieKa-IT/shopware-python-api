# Client and transport

[Documentation](../index.md)

Examples assume an authenticated `shop` context with a `products` entity set;
`products` is shorthand for `shop.products`. See [models and contexts](models.md).

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
    params={"extension": "svg", "fileName": "green-tshirt"},
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
