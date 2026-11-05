# shopware-admin-python

This is an independent Python library repository inside the ArcusShop umbrella.
Keep library code, examples, and implementation documentation here. Use uv for
dependencies and commands. Commit this repository independently of ArcusShop.

Run `uv run pytest`, `uv run mypy`, `uv run pyright`, and `uv run ruff check .`.
HTTP tests must use HTTPX MockTransport; never require a live shop or credentials.
Keep missing fields distinct from null, writes explicit, and query construction
free of HTTP requests. Do not add generated models or a scaffolder to the runtime.
