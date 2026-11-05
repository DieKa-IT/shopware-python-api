"""HTTP schema discovery and reproducible offline bundles."""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from . import ScaffoldError
from .catalog import Json, object_value
from .generator import OWNER, digest, json_text
from .writer import atomic_write, safe_path

SCHEMA_FILES = ("openapi.json", "entity-schema.json")


@dataclass(frozen=True)
class Auth:
    client_id: str | None = None
    client_secret: str | None = field(default=None, repr=False)
    access_token: str | None = field(default=None, repr=False)

    def validate(self) -> None:
        if (self.client_id is None) != (self.client_secret is None):
            raise ScaffoldError(
                "Both SHOPWARE_API_CLIENT_ID and SHOPWARE_API_CLIENT_SECRET are required"
            )
        if self.access_token is not None and self.client_id is not None:
            raise ScaffoldError(
                "Choose either integration credentials or SHOPWARE_API_ACCESS_TOKEN"
            )
        if any(value == "" for value in (self.client_id, self.client_secret, self.access_token)):
            raise ScaffoldError("Authentication values cannot be empty")


@dataclass(frozen=True)
class SchemaBundle:
    openapi: Json
    dal: Json

    @property
    def hashes(self) -> Json:
        return {
            "openapi.json": digest(json_text(self.openapi)),
            "entity-schema.json": digest(json_text(self.dal)),
        }

    @classmethod
    def load(cls, directory: Path) -> "SchemaBundle":
        try:
            docs = [
                object_value(json.loads((directory / name).read_text(encoding="utf-8")), name)
                for name in SCHEMA_FILES
            ]
            bundle = cls(*docs)
            provenance = directory / "manifest.json"
            if provenance.exists():
                metadata = object_value(
                    json.loads(provenance.read_text(encoding="utf-8")), "Snapshot manifest"
                )
                if metadata.get("owner") != OWNER or metadata.get("hashes") != bundle.hashes:
                    raise ScaffoldError(
                        "Snapshot manifest ownership/hashes do not match the schema files"
                    )
            return bundle
        except (ValueError, OSError) as error:
            raise ScaffoldError(f"Cannot load schema bundle {directory}: {error}") from error

    def save(self, directory: Path, force: bool = False) -> None:
        content = {
            "openapi.json": json_text(self.openapi),
            "entity-schema.json": json_text(self.dal),
            "manifest.json": json_text(
                {
                    "owner": OWNER,
                    "format": 1,
                    "hashes": self.hashes,
                    "shopware_version": self.openapi.get("info", {}).get("version"),
                }
            ),
        }
        existing = [name for name in content if safe_path(directory.absolute(), name).exists()]
        if existing:
            # An arbitrary schema directory must not be adopted by --force.
            self.load(directory)
            if not (directory / "manifest.json").exists():
                raise ScaffoldError(
                    "Refusing to overwrite a snapshot without an ownership manifest"
                )
            if not force:
                raise ScaffoldError(
                    "Snapshot already exists; use --force to replace this owned bundle"
                )
        for name in (*SCHEMA_FILES, "manifest.json"):
            atomic_write(safe_path(directory.absolute(), name), content[name])


class SchemaClient:
    def __init__(
        self,
        url: str,
        auth: Auth | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        try:
            parsed = httpx.URL(url)
        except httpx.InvalidURL as error:
            raise ScaffoldError("Invalid shop URL") from error
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.host
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ScaffoldError(
                "Use an HTTP(S) shop base URL without credentials, query, or fragment"
            )
        if not math.isfinite(timeout) or timeout <= 0:
            raise ScaffoldError("Timeout must be a positive finite number")
        self.auth = auth or Auth()
        self.auth.validate()
        self.http = httpx.Client(
            base_url=url.rstrip("/") + "/", timeout=timeout, transport=transport
        )

    def __enter__(self) -> "SchemaClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.http.close()

    def _request(
        self, method: str, path: str, token: str | None = None, payload: Json | None = None
    ) -> Json:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self.http.request(method, path, json=payload, headers=headers)
        except httpx.HTTPError as error:
            raise ScaffoldError(
                f"Schema HTTP transport failed for {method} {path.split('?')[0]}"
            ) from error
        if not response.is_success:
            # Do not echo response bodies, tokens, or OAuth payloads into diagnostics.
            raise ScaffoldError(
                f"Shopware returned HTTP {response.status_code} for {method} {path.split('?')[0]}"
            )
        try:
            return object_value(response.json(), f"Response to {path}")
        except ValueError as error:
            raise ScaffoldError(f"Shopware returned invalid JSON for {path}") from error

    def fetch(self) -> SchemaBundle:
        token = self.auth.access_token
        if self.auth.client_id is not None:
            response = self._request(
                "POST",
                "api/oauth/token",
                payload={
                    "grant_type": "client_credentials",
                    "client_id": self.auth.client_id,
                    "client_secret": self.auth.client_secret,
                },
            )
            token = response.get("access_token")
            if not isinstance(token, str) or not token:
                raise ScaffoldError("Shopware returned no OAuth access token")
        openapi = self._request("GET", "api/_info/openapi3.json?type=jsonapi", token)
        dal = self._request("GET", "api/_info/entity-schema.json", token)
        return SchemaBundle(openapi, dal)
