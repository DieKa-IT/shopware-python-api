import json

import httpx
import pytest

from shopware_admin_scaffold import ScaffoldError
from shopware_admin_scaffold.schema_client import Auth, SchemaBundle, SchemaClient


def test_integration_authentication_and_subdirectory_base_url(bundle):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/oauth/token"):
            assert json.loads(request.content) == {
                "grant_type": "client_credentials",
                "client_id": "key",
                "client_secret": "secret",
            }
            return httpx.Response(200, json={"access_token": "token"})
        assert request.headers["Authorization"] == "Bearer token"
        if request.url.path.endswith("/openapi3.json"):
            assert request.url.params["type"] == "jsonapi"
            return httpx.Response(200, json=bundle.openapi)
        return httpx.Response(200, json=bundle.dal)

    with SchemaClient(
        "https://shop.example/sub/", Auth("key", "secret"), transport=httpx.MockTransport(handler)
    ) as client:
        assert client.fetch() == bundle
    assert [request.url.path for request in requests] == [
        "/sub/api/oauth/token",
        "/sub/api/_info/openapi3.json",
        "/sub/api/_info/entity-schema.json",
    ]


@pytest.mark.parametrize("auth", [Auth(), Auth(access_token="token")])
def test_anonymous_and_external_tokens_skip_oauth(bundle, auth):
    requests = []

    def handler(request):
        requests.append(request)
        assert ("Authorization" in request.headers) == bool(auth.access_token)
        return httpx.Response(
            200, json=bundle.openapi if request.url.path.endswith("openapi3.json") else bundle.dal
        )

    with SchemaClient(
        "https://shop.example", auth, transport=httpx.MockTransport(handler)
    ) as client:
        client.fetch()
    assert len(requests) == 2


def test_rejected_credentials_never_fall_back_or_leak_response_body():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(401, text="secret token credentials")

    with SchemaClient(
        "https://shop.example", Auth("key", "secret"), transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(ScaffoldError, match="HTTP 401") as error:
            client.fetch()
    assert "secret" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "auth",
    [
        Auth("key"),
        Auth(client_secret="secret"),
        Auth("key", "secret", "token"),
        Auth(access_token=""),
    ],
)
def test_bad_auth_settings_fail_before_http(auth):
    with pytest.raises(ScaffoldError):
        SchemaClient("https://shop.example", auth)


@pytest.mark.parametrize(
    "url", ["file:///tmp", "https://key:secret@shop.example", "https://shop.example?secret=x"]
)
def test_invalid_urls_are_rejected(url):
    with pytest.raises(ScaffoldError):
        SchemaClient(url)


def test_invalid_json_and_http_failure_are_actionable():
    with SchemaClient(
        "https://shop.example",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"not JSON")),
    ) as client:
        with pytest.raises(ScaffoldError, match="invalid JSON"):
            client.fetch()


def test_snapshot_hashes_ownership_and_force(tmp_path, bundle):
    directory = tmp_path / "schemas"
    bundle.save(directory)
    assert SchemaBundle.load(directory) == bundle
    assert "secret" not in (directory / "manifest.json").read_text()
    with pytest.raises(ScaffoldError, match="--force"):
        bundle.save(directory)
    bundle.save(directory, force=True)
    (directory / "openapi.json").write_text("{}")
    with pytest.raises(ScaffoldError, match="hashes"):
        SchemaBundle.load(directory)


def test_snapshot_cannot_overwrite_an_unowned_directory(tmp_path, bundle):
    (tmp_path / "openapi.json").write_text("{}")
    with pytest.raises(ScaffoldError):
        bundle.save(tmp_path, force=True)
    assert (tmp_path / "openapi.json").read_text() == "{}"
