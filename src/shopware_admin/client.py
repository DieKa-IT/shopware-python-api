"""Synchronous Admin API transport, typed repositories, and prepared requests."""

from __future__ import annotations

import copy
import json
import re
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Any, Generic, Self, TypeVar, cast
from uuid import uuid4

import httpx

from .criteria import Criteria, Patch, _positive
from .errors import (
    CardinalityError,
    MappingError,
    QueryError,
    ResponseError,
    ShopwareApiError,
    TransportError,
)
from .expressions import Predicate, Sort, _snapshot
from .mapping import Entity, ModelRegistry

E = TypeVar("E", bound=Entity)
R = TypeVar("R", bound=Entity)
T = TypeVar("T")
QueryParams = Mapping[str, str | int | float | bool | None]
_NOT_FOUND = object()


@dataclass(frozen=True)
class IntegrationAuth:
    """Integration client ID and secret used to obtain and refresh access tokens."""

    client_id: str
    client_secret: str = field(repr=False)


@dataclass(frozen=True)
class AccessToken:
    """An externally managed bearer token; the client does not refresh it."""

    token: str = field(repr=False)


@dataclass(frozen=True)
class RequestContext:
    """Language, version, and inheritance settings applied as request headers."""

    language_id: str | None = None
    version_id: str | None = None
    inheritance: bool = False

    def headers(self) -> dict[str, str]:
        """Return validated Shopware context headers without authentication."""
        headers: dict[str, str] = {}
        if self.language_id is not None:
            headers["sw-language-id"] = _id(self.language_id)
        if self.version_id is not None:
            headers["sw-version-id"] = _id(self.version_id)
        if self.inheritance:
            headers["sw-inheritance"] = "1"
        return headers


class CountMode(IntEnum):
    """Search totals: NONE omits totals, EXACT counts, NEXT_PAGES estimates."""

    NONE = 0
    EXACT = 1
    NEXT_PAGES = 2


def _id(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{32}", value) is None:
        raise MappingError("Entity IDs must be 32 hexadecimal characters")
    return value.lower()


@dataclass(frozen=True)
class SearchResult(Generic[E]):
    """A typed result page with items, pagination, count metadata, and aggregations."""

    items: list[E]
    total: int | None
    total_is_exact: bool
    aggregations: dict[str, Any]
    page: int
    size: int


@dataclass(frozen=True, eq=False)
class PreparedRequest(Generic[T]):
    """A payload and header snapshot that sends no request until execute() is called."""

    method: str
    path: str
    _body: str | None = field(repr=False)
    _headers: tuple[tuple[str, str], ...] = field(repr=False)
    _executor: Callable[[PreparedRequest[T]], T] = field(repr=False)

    @property
    def json(self) -> dict[str, Any] | None:
        """A defensive copy of the exact payload used on every execution."""
        return None if self._body is None else cast(dict[str, Any], json.loads(self._body))

    @property
    def headers(self) -> dict[str, str]:
        """Context headers only; access tokens and credentials are never previewed."""
        return dict(self._headers)

    def execute(self) -> T:
        """Send the request and return its result; each call sends it again."""
        return self._executor(self)


class _Connection:
    def __init__(
        self,
        base_url: str,
        auth: IntegrationAuth | AccessToken,
        timeout: float,
        transport: httpx.BaseTransport | None,
    ):
        url = httpx.URL(base_url)
        if url.scheme not in ("http", "https") or not url.host or url.username or url.password:
            raise MappingError("Use an HTTP(S) shop URL without embedded credentials")
        self.http = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/", timeout=timeout, transport=transport
        )
        self.auth = auth
        self.token: str | None = auth.token if isinstance(auth, AccessToken) else None
        self.expires_at = float("inf") if isinstance(auth, AccessToken) else 0.0
        self.lock = threading.Lock()

    def bearer(self, rejected: str | None = None) -> str:
        with self.lock:
            if (
                rejected is not None
                and self.token == rejected
                and isinstance(self.auth, IntegrationAuth)
            ):
                self.token = None
            if self.token is not None and time.monotonic() < self.expires_at:
                return self.token
            if not isinstance(self.auth, IntegrationAuth):
                raise ResponseError("No usable access token")
            payload = self.send(
                "POST",
                "/api/oauth/token",
                {
                    "grant_type": "client_credentials",
                    "client_id": self.auth.client_id,
                    "client_secret": self.auth.client_secret,
                },
                {},
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
                raise ResponseError("Shopware returned no OAuth access token")
            token = cast(str, payload["access_token"])
            lifetime = payload.get("expires_in", 600)
            if not token or type(lifetime) not in (int, float) or lifetime <= 0:
                raise ResponseError("Invalid OAuth token or expiration")
            self.token = token
            self.expires_at = time.monotonic() + lifetime * 0.9
            return token

    def send(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
        *,
        allow_not_found: bool = False,
        params: QueryParams | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
    ) -> Any:
        if not path.startswith("/api/") or ".." in path or "?" in path:
            raise MappingError("Requests require a relative /api/ path without query parameters")
        try:
            response = self.http.request(
                method,
                path.lstrip("/"),
                json=payload,
                params=params,
                content=content,
                headers={
                    "Accept": "application/json",
                    **headers,
                    **({"Content-Type": content_type} if content_type is not None else {}),
                },
            )
        except httpx.HTTPError as error:
            raise TransportError(f"HTTP transport failed for {method} {path}") from error
        if allow_not_found and response.status_code == 404:
            return _NOT_FOUND
        if not response.is_success:
            errors: list[dict[str, Any]] = []
            try:
                body = response.json()
                raw_errors = body.get("errors", []) if isinstance(body, dict) else []
                errors = [item for item in raw_errors if isinstance(item, dict)]
            except (ValueError, TypeError):
                pass
            raise ShopwareApiError(method, path, response.status_code, errors)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise ResponseError(f"Invalid JSON response for {method} {path}") from error


class Client:
    """Synchronous Admin API client with pooled HTTP connections and authentication."""

    def __init__(
        self,
        base_url: str,
        auth: IntegrationAuth | AccessToken,
        *,
        models: list[type[Entity]] | None = None,
        context: RequestContext | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        """Configure the connection and register models without making HTTP requests."""
        self.registry = ModelRegistry([*self._declared_models(), *(models or [])])
        self.context = context if context is not None else RequestContext()
        self.context.headers()
        self._connection = _Connection(base_url, auth, timeout, transport)
        self._owns_connection = True

    @classmethod
    def _declared_models(cls) -> list[type[Entity]]:
        return []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the owned connection pool; context views leave the shared pool open."""
        if self._owns_connection:
            self._connection.http.close()

    def with_context(self, context: RequestContext) -> Self:
        """A shallow view preserving the client type and sharing its connection and registry."""
        context.headers()
        view = copy.copy(self)
        view.context = context
        view._owns_connection = False
        return view

    def set(self, model: type[E]) -> Repository[E]:
        """Register a model and return its typed repository without making a request."""
        self.registry.register(model)
        return Repository(self, self.registry.resolve(model))

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        params: QueryParams | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
    ) -> Any:
        """Escape hatch for action endpoints; authentication and error handling still apply."""
        if payload is not None and content is not None:
            raise MappingError("Use either a JSON payload or binary content")
        if content is not None and not isinstance(content, bytes):
            raise MappingError("Binary content must be bytes")
        if content_type is not None and content is None:
            raise MappingError("content_type requires binary content")
        return self._send(
            method,
            path,
            copy.deepcopy(payload),
            self.context.headers(),
            params=None if params is None else dict(params),
            content=content,
            content_type=content_type,
        )

    def _send(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
        *,
        allow_not_found: bool = False,
        params: QueryParams | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
    ) -> Any:
        token = self._connection.bearer()
        try:
            return self._connection.send(
                method,
                path,
                payload,
                {**headers, "Authorization": f"Bearer {token}"},
                allow_not_found=allow_not_found,
                params=params,
                content=content,
                content_type=content_type,
            )
        except ShopwareApiError as error:
            if error.status != 401 or not isinstance(self._connection.auth, IntegrationAuth):
                raise
            # A rejected token means the request was not authorized. Refresh once only.
            token = self._connection.bearer(rejected=token)
            return self._connection.send(
                method,
                path,
                payload,
                {**headers, "Authorization": f"Bearer {token}"},
                allow_not_found=allow_not_found,
                params=params,
                content=content,
                content_type=content_type,
            )


class Repository(Generic[E]):
    """Typed entity search and explicit CRUD operations for one model."""

    def __init__(self, client: Client, model: type[E]):
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", model.__route__) is None:
            raise MappingError("Invalid entity API route")
        self.client = client
        self.model = model
        self.path = f"/api/{model.__route__}"

    def search(self) -> Query[E]:
        """Build an unfiltered query without making an HTTP request."""
        return Query(self, Criteria(self.model))

    def where(self, *predicates: Predicate) -> Query[E]:
        """Build a query with AND-combined predicates without making a request."""
        return self.search().where(*predicates)

    def filter(self, *predicates: Predicate) -> Query[E]:
        """Alias for where(); build a filtered query without making a request."""
        return self.where(*predicates)

    def patch(self) -> Patch[E]:
        """Start an immutable patch selecting only explicitly set fields."""
        return Patch(self.model)

    def _prepare(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        executor: Callable[[PreparedRequest[T]], T],
    ) -> PreparedRequest[T]:
        return PreparedRequest(
            method,
            path,
            None if payload is None else _snapshot(payload),
            tuple(self.client.context.headers().items()),
            executor,
        )

    def _send(self, request: PreparedRequest[Any], *, allow_not_found: bool = False) -> Any:
        return self.client._send(
            request.method,
            request.path,
            request.json,
            request.headers,
            allow_not_found=allow_not_found,
        )

    def prepare_get(self, entity_id: str) -> PreparedRequest[E | None]:
        """Prepare a read by ID; execution returns an entity or None for HTTP 404."""

        def execute(request: PreparedRequest[E | None]) -> E | None:
            data = self._send(request, allow_not_found=True)
            if data is _NOT_FOUND:
                return None
            if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
                raise ResponseError("Detail response requires a data object")
            return self.model.from_data(data["data"], registry=self.client.registry)

        return self._prepare("GET", f"{self.path}/{_id(entity_id)}", None, execute)

    def get(self, entity_id: str) -> E | None:
        """Fetch an entity by ID; return None only for HTTP 404."""
        return self.prepare_get(entity_id).execute()

    def prepare_create(self, entity: E) -> PreparedRequest[str]:
        """Validate and snapshot creation values, fixing the ID before execution."""
        if not isinstance(entity, self.model):
            raise MappingError("Create requires an instance of the repository model")
        for name, descriptor in self.model.__fields__.items():
            if descriptor.required_on_create and entity._values.get(name) is None:
                raise MappingError(f"Create requires {name}")
        payload = entity.to_payload()
        entity_id = _id(payload["id"]) if "id" in payload else uuid4().hex
        payload["id"] = entity_id

        def execute(request: PreparedRequest[str]) -> str:
            self._send(request)
            primary = next(
                (item for item in self.model.__fields__.values() if item.json_path == ("id",)), None
            )
            if primary is not None:
                entity._values[primary.name] = entity_id
            return entity_id

        return self._prepare("POST", self.path, payload, execute)

    def create(self, entity: E) -> str:
        """Use an explicit/client-generated ID; return it after the server accepts the write."""
        return self.prepare_create(entity).execute()

    def prepare_update(self, entity_id: str, *changes: Patch[E]) -> PreparedRequest[None]:
        """Combine and snapshot selected fields without sending an update request."""
        patch = Patch(self.model)
        for change in changes:
            patch = patch._merge(change)
        payload = patch.to_payload()
        if "id" in payload:
            raise MappingError("An update cannot change the primary ID")

        def execute(request: PreparedRequest[None]) -> None:
            self._send(request)

        return self._prepare("PATCH", f"{self.path}/{_id(entity_id)}", payload, execute)

    def update(self, entity_id: str, *changes: Patch[E]) -> None:
        """Send all selected fields in one PATCH request; return None after success."""
        self.prepare_update(entity_id, *changes).execute()

    def delete(self, entity_id: str) -> None:
        """Delete the entity by ID immediately; return None after success."""
        self.client._send(
            "DELETE", f"{self.path}/{_id(entity_id)}", None, self.client.context.headers()
        )


@dataclass(frozen=True, eq=False)
class Query(Generic[E]):
    """An immutable query description; building it never sends HTTP requests."""

    repository: Repository[E]
    criteria: Criteria[E]

    def where(self, *predicates: Predicate) -> Query[E]:
        """Return a query with additional predicates combined using AND."""
        return replace(self, criteria=self.criteria.where(*predicates))

    def filter(self, *predicates: Predicate) -> Query[E]:
        """Alias for where(); return a query with additional AND-combined predicates."""
        return self.where(*predicates)

    def order_by(self, *sorts: Sort) -> Query[E]:
        """Return a query with sort expressions appended in priority order."""
        return replace(self, criteria=self.criteria.order_by(*sorts))

    def limit(self, size: int) -> Query[E]:
        """Return a query with a positive per-request result limit; not for iter()."""
        return replace(self, criteria=self.criteria.limit(size))

    def load(self, association: type[R], *, criteria: Criteria[R] | None = None) -> Query[E]:
        """Request association data, optionally restricted by related-entity criteria."""
        return replace(self, criteria=self.criteria.load(association, criteria=criteria))

    def prepare(
        self, *, page: int = 1, size: int = 100, count: CountMode = CountMode.NONE
    ) -> PreparedRequest[SearchResult[E]]:
        """Snapshot a search request without sending it; pages and sizes start at one."""
        _positive(page, "page")
        _positive(size, "size")
        body = self.criteria.to_payload()
        page_size = body.get("limit", size)
        body.update({"page": page, "limit": page_size, "total-count-mode": int(count)})

        def execute(request: PreparedRequest[SearchResult[E]]) -> SearchResult[E]:
            result = self.repository._send(request)
            if not isinstance(result, dict) or not isinstance(result.get("data"), list):
                raise ResponseError("Search response requires a data array")
            total = result.get("total") if count != CountMode.NONE else None
            aggregations = result.get("aggregations", {})
            # PHP serializes an empty associative collection as an empty array.
            if aggregations == []:
                aggregations = {}
            if total is not None and type(total) is not int:
                raise ResponseError("Search total must be an integer")
            if count == CountMode.EXACT and total is None:
                raise ResponseError("Exact-count search returned no total")
            if not isinstance(aggregations, dict):
                raise ResponseError("Search aggregations must be an object")
            model = self.repository.model
            return SearchResult(
                [
                    model.from_data(item, registry=self.repository.client.registry)
                    for item in result["data"]
                ],
                total,
                count == CountMode.EXACT,
                aggregations,
                page,
                page_size,
            )

        return self.repository._prepare(
            "POST", f"/api/search/{self.repository.model.__route__}", body, execute
        )

    def fetch_page(
        self, *, page: int = 1, size: int = 100, count: CountMode = CountMode.NONE
    ) -> SearchResult[E]:
        """Execute a search and return one typed page; totals are omitted by default."""
        return self.prepare(page=page, size=size, count=count).execute()

    def first(self) -> E | None:
        """Fetch at most one matching entity; return None when there is no match."""
        items = self.limit(1).fetch_page().items
        return items[0] if items else None

    def one(self) -> E:
        """Fetch one match or raise CardinalityError for zero or multiple matches."""
        items = self.limit(2).fetch_page().items
        if len(items) != 1:
            raise CardinalityError(
                f"Expected one {self.repository.model.__name__}, found {len(items)}"
            )
        return items[0]

    def ids(self, *, page: int = 1, size: int = 100) -> list[str]:
        """Search for one page of matching IDs without loading entity associations."""
        _positive(page, "page")
        _positive(size, "size")
        body = self.criteria.to_payload()
        body.pop("associations", None)
        body.update({"page": page, "limit": body.get("limit", size), "total-count-mode": 0})
        result = self.repository.client._send(
            "POST",
            f"/api/search-ids/{self.repository.model.__route__}",
            body,
            self.repository.client.context.headers(),
        )
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise ResponseError("IDs search response requires a data array")
        try:
            return [_id(value) for value in result["data"]]
        except MappingError as error:
            raise ResponseError("IDs search returned an invalid ID") from error

    def iter(self, *, page_size: int = 500) -> Iterator[E]:
        """Traverse pages with an ID tie-breaker. This is not a server snapshot."""
        _positive(page_size, "page_size")
        if self.criteria._limit is not None:
            raise QueryError("iter() uses page_size; do not combine it with limit()")
        id_field = next(
            (
                item
                for item in self.repository.model.__fields__.values()
                if item.json_path == ("id",)
            ),
            None,
        )
        if id_field is None:
            raise MappingError("Pagination requires a mapped primary ID")
        sorts = self.criteria._sorts
        query = (
            self
            if any(item.field == id_field.criteria_path for item in sorts)
            else self.order_by(
                Sort(self.repository.model.__entity__, id_field.criteria_path, "ASC")
            )
        )
        page = 1
        while True:
            result = query.fetch_page(page=page, size=page_size)
            yield from result.items
            if len(result.items) < page_size:
                return
            page += 1
