# Development

[Documentation](index.md)


```bash
uv sync --locked
uv run pytest
uv run mypy
uv run pyright
uv run ruff check .
uv run ruff format --check .
uv build
```

Tests use HTTPX MockTransport, not a live shop. `tests/typing_contract.py` checks
typed constructors, values, nested field traversal, repositories, query results,
and invalid inputs with both mypy and Pyright. Live integration compatibility
with your particular Shopware version and installed plugins remains to be tested.


See [releasing packages](releasing.md) for the release workflow.
