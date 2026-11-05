import json

import httpx
import pytest

from examples.models import Category, Product
from shopware_admin import (
    AccessToken,
    CardinalityError,
    Client,
    CountMode,
    IntegrationAuth,
    MappingError,
    QueryError,
    RequestContext,
    ResponseError,
    ShopwareApiError,
    TransportError,
)

ID = "1" * 32


def client_for(handler, *, auth=None, context=None):
    return Client(
        "https://shop.example",
        auth or AccessToken("test-token"),
        models=[Product],
        context=context,
        transport=httpx.MockTransport(handler),
    )


def fresh_product():
    return Product(
        name="O-ring",
        product_number="ARC-1",
        stock=10,
        tax_id="2" * 32,
        price=[{"currencyId": "3" * 32, "gross": 1.19, "net": 1.0, "linked": True}],
    )


def test_search_sends_shopware_criteria_and_returns_typed_results():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "total": 1,
                "data": [{"id": ID, "name": "O-ring", "stock": 12}],
                "aggregations": {"stock": {"sum": 12}},
            },
        )

    with client_for(handler) as client:
        query = client.set(Product).where(Product.stock > 0).order_by(Product.id.asc())
        prepared = query.prepare(page=2, size=10, count=CountMode.EXACT)
        assert requests == []
        preview = prepared.json
        preview["filter"][0]["parameters"]["gt"] = 100
        result = prepared.execute()
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/search/product"
    assert requests[0].headers["Authorization"] == "Bearer test-token"
    body = json.loads(requests[0].content)
    assert body["filter"] == [{"type": "range", "field": "stock", "parameters": {"gt": 0}}]
    assert (body["page"], body["limit"], body["total-count-mode"]) == (2, 10, 1)
    assert isinstance(result.items[0], Product)
    assert result.items[0].stock == 12
    assert result.total == 1
    assert result.total_is_exact
    assert result.aggregations == {"stock": {"sum": 12}}


def test_search_accepts_php_empty_aggregations_array():
    with client_for(
        lambda _: httpx.Response(200, json={"data": [{"id": ID}], "aggregations": []})
    ) as client:
        result = client.set(Product).search().fetch_page()
    assert result.items[0].id == ID
    assert result.aggregations == {}


@pytest.mark.parametrize("aggregations", [[{"name": "stock"}], None, "invalid"])
def test_search_rejects_invalid_aggregations(aggregations):
    with client_for(
        lambda _: httpx.Response(200, json={"data": [], "aggregations": aggregations})
    ) as client:
        with pytest.raises(ResponseError, match="aggregations must be an object"):
            client.set(Product).search().fetch_page()


def test_total_count_modes_do_not_claim_unrequested_exact_totals():
    with client_for(lambda _: httpx.Response(200, json={"total": 501, "data": []})) as client:
        query = client.set(Product).search()
        result = query.fetch_page()
        assert result.total is None
        assert not result.total_is_exact
        result = query.fetch_page(count=CountMode.NEXT_PAGES)
        assert result.total == 501
        assert not result.total_is_exact


def test_detail_get_and_not_found():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("2" * 32):
            return httpx.Response(404, json={"errors": []})
        return httpx.Response(200, json={"data": {"id": ID, "stock": 4}})

    with client_for(handler) as client:
        products = client.set(Product)
        assert products.get(ID).stock == 4
        assert products.get("2" * 32) is None
        with pytest.raises(MappingError):
            products.get("1234")
    assert len(requests) == 2


def test_patch_sends_only_selected_fields_including_null():
    requests = []
    with client_for(lambda request: requests.append(request) or httpx.Response(204)) as client:
        products = client.set(Product)
        patch = products.patch().set(Product.name, "A").set(Product.parent_id, None)
        prepared = products.prepare_update(ID, patch)
        patch = patch.set(Product.name, "B")
        prepared.execute()
    assert requests[0].method == "PATCH"
    assert requests[0].url.path == f"/api/product/{ID}"
    assert json.loads(requests[0].content) == {"name": "A", "parentId": None}


def test_create_snapshots_payload_and_generates_a_stable_id_before_execution():
    requests = []
    with client_for(lambda request: requests.append(request) or httpx.Response(204)) as client:
        product = fresh_product()
        prepared = client.set(Product).prepare_create(product)
        assert not product.is_loaded(Product.id)
        product.name = "Edited after preparation"
        entity_id = prepared.execute()
        assert product.id == entity_id
        assert prepared.json["id"] == entity_id
    body = json.loads(requests[0].content)
    assert body["name"] == "O-ring"
    assert body["productNumber"] == "ARC-1"
    assert body["id"] == entity_id
    assert len(entity_id) == 32


def test_create_preserves_explicit_id_and_requires_declared_creation_fields():
    requests = []
    with client_for(lambda request: requests.append(request) or httpx.Response(204)) as client:
        product = fresh_product()
        product.id = ID
        assert client.set(Product).create(product) == ID
        with pytest.raises(MappingError, match="Create requires"):
            client.set(Product).create(Product(name="incomplete"))
    assert json.loads(requests[0].content)["id"] == ID


def test_create_preserves_server_defaults_and_only_sends_explicit_nulls():
    requests = []
    with client_for(lambda request: requests.append(request) or httpx.Response(204)) as client:
        products = client.set(Product)
        omitted = fresh_product()
        omitted.stock = 0
        assert omitted.active is None
        assert omitted.parent_id is None
        products.create(omitted)
        explicit = fresh_product()
        explicit.active = None
        products.create(explicit)
    omitted_body = json.loads(requests[0].content)
    assert "active" not in omitted_body
    assert "parentId" not in omitted_body
    assert omitted_body["stock"] == 0
    assert json.loads(requests[1].content)["active"] is None


def test_primary_id_cannot_be_changed_in_a_patch():
    with client_for(lambda _: pytest.fail("No HTTP expected")) as client:
        products = client.set(Product)
        with pytest.raises(MappingError):
            products.update(ID, products.patch().set(Product.id, "2" * 32))


def test_oauth_token_is_reused_and_credentials_are_not_in_previews():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/oauth/token":
            assert json.loads(request.content) == {
                "grant_type": "client_credentials",
                "client_id": "integration",
                "client_secret": "secret",
            }
            return httpx.Response(200, json={"access_token": "token", "expires_in": 600})
        assert request.headers["Authorization"] == "Bearer token"
        return httpx.Response(200, json={"data": []})

    auth = IntegrationAuth("integration", "secret")
    assert "secret" not in repr(auth)
    with client_for(handler, auth=auth) as client:
        prepared = client.set(Product).search().prepare()
        assert prepared.headers == {}
        assert "secret" not in repr(prepared)
        prepared.execute()
        prepared.execute()
    assert len(requests) == 3


def test_rejected_token_is_refreshed_once_with_the_same_request_payload():
    token_requests = 0
    searches = []

    def handler(request):
        nonlocal token_requests
        if request.url.path == "/api/oauth/token":
            token_requests += 1
            return httpx.Response(200, json={"access_token": f"token-{token_requests}"})
        searches.append(request)
        if len(searches) == 1:
            return httpx.Response(401, json={"errors": []})
        return httpx.Response(200, json={"data": []})

    with client_for(handler, auth=IntegrationAuth("integration", "secret")) as client:
        client.set(Product).where(Product.stock > 0).fetch_page()
    assert token_requests == 2
    assert searches[0].content == searches[1].content
    assert searches[1].headers["Authorization"] == "Bearer token-2"


def test_a_second_401_is_not_retried_forever():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": str(len(requests))})
        return httpx.Response(401, json={"errors": [{"code": "unauthorized"}]})

    with client_for(handler, auth=IntegrationAuth("integration", "secret")) as client:
        with pytest.raises(ShopwareApiError) as error:
            client.set(Product).search().fetch_page()
        assert error.value.status == 401
    assert len(requests) == 4


def test_static_tokens_are_not_refreshed_on_401():
    requests = []
    with client_for(lambda request: requests.append(request) or httpx.Response(401)) as client:
        with pytest.raises(ShopwareApiError):
            client.set(Product).search().fetch_page()
    assert len(requests) == 1


def test_expired_integration_token_is_refreshed_proactively():
    token_requests = 0

    def handler(request):
        nonlocal token_requests
        if request.url.path == "/api/oauth/token":
            token_requests += 1
            return httpx.Response(
                200, json={"access_token": f"token-{token_requests}", "expires_in": 100}
            )
        return httpx.Response(200, json={"data": []})

    with client_for(handler, auth=IntegrationAuth("integration", "secret")) as client:
        client.set(Product).search().fetch_page()
        client._connection.expires_at = 0
        client.set(Product).search().fetch_page()
    assert token_requests == 2


def test_context_views_share_tokens_but_snapshot_request_headers():
    requests = []
    with client_for(
        lambda request: requests.append(request) or httpx.Response(200, json={"data": []})
    ) as client:
        localized = client.with_context(RequestContext(language_id="2" * 32, inheritance=True))
        prepared = localized.set(Product).search().prepare()
        localized.context = RequestContext(language_id="3" * 32)
        localized.close()
        prepared.execute()
        client.set(Product).search().fetch_page()
    assert requests[0].headers["sw-language-id"] == "2" * 32
    assert requests[0].headers["sw-inheritance"] == "1"
    assert "sw-language-id" not in requests[1].headers


def test_iter_paginates_with_id_tie_breaker_and_no_exact_counts():
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        data = [{"id": ID, "stock": 2}, {"id": "2" * 32, "stock": 3}] if body["page"] == 1 else []
        return httpx.Response(200, json={"data": data})

    with client_for(handler) as client:
        query = client.set(Product).search().order_by(Product.name.asc())
        items = list(query.iter(page_size=2))
        with pytest.raises(QueryError):
            list(query.limit(1).iter())
    assert [item.stock for item in items] == [2, 3]
    assert [request["page"] for request in requests] == [1, 2]
    assert requests[0]["sort"][-1]["field"] == "id"
    assert requests[0]["total-count-mode"] == 0


def test_ids_uses_search_ids_and_omits_associations():
    requests = []
    with client_for(
        lambda request: requests.append(request) or httpx.Response(200, json={"data": [ID]})
    ) as client:
        result = client.set(Product).where(Product.stock > 0).load(Product.categories).ids(size=10)
    assert result == [ID]
    assert requests[0].url.path == "/api/search-ids/product"
    assert "associations" not in json.loads(requests[0].content)


@pytest.mark.parametrize("data", [[], [{"id": ID}], [{"id": ID}, {"id": "2" * 32}]])
def test_one_checks_cardinality_without_fetching_all_rows(data):
    requests = []
    with client_for(
        lambda request: requests.append(request) or httpx.Response(200, json={"data": data})
    ) as client:
        query = client.set(Product).search()
        if len(data) == 1:
            assert query.one().id == ID
        else:
            with pytest.raises(CardinalityError):
                query.one()
    assert json.loads(requests[0].content)["limit"] == 2


def test_first_returns_none_for_an_empty_search():
    with client_for(lambda _: httpx.Response(200, json={"data": []})) as client:
        assert client.set(Product).search().first() is None


def test_api_write_errors_are_structured_and_never_retried():
    requests = []
    error_data = [
        {"code": "FRAMEWORK__WRITE_CONSTRAINT_VIOLATION", "source": {"pointer": "/stock"}}
    ]

    def handler(request):
        requests.append(request)
        return httpx.Response(500, json={"errors": error_data})

    with client_for(handler) as client:
        with pytest.raises(ShopwareApiError) as error:
            client.set(Product).create(fresh_product())
        assert error.value.status == 500
        assert error.value.errors == error_data
    assert len(requests) == 1


def test_write_transport_errors_are_not_retried():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timeout", request=request)

    with client_for(handler) as client:
        with pytest.raises(TransportError):
            client.set(Product).create(fresh_product())
    assert attempts == 1


@pytest.mark.parametrize("payload", [{}, {"data": None}, {"data": {}}, {"data": [None]}])
def test_malformed_search_responses_fail_explicitly(payload):
    with client_for(lambda _: httpx.Response(200, json=payload)) as client:
        with pytest.raises((ResponseError, MappingError)):
            client.set(Product).search().fetch_page()


def test_invalid_json_success_response_fails_explicitly():
    with client_for(lambda _: httpx.Response(200, text="not json")) as client:
        with pytest.raises(ResponseError):
            client.set(Product).search().fetch_page()


def test_empty_successful_detail_response_is_not_treated_as_not_found():
    with client_for(lambda _: httpx.Response(204)) as client:
        with pytest.raises(ResponseError):
            client.set(Product).get(ID)


def test_raw_action_requests_keep_transport_behavior():
    requests = []
    with client_for(lambda request: requests.append(request) or httpx.Response(204)) as client:
        assert (
            client.request("POST", "/api/_action/sync", {"products": {"action": "upsert"}}) is None
        )
    assert requests[0].url.path == "/api/_action/sync"


def test_raw_request_sends_binary_content_query_parameters_and_context():
    requests = []
    with client_for(
        lambda request: requests.append(request) or httpx.Response(204),
        context=RequestContext(language_id="2" * 32),
    ) as client:
        result = client.request(
            "POST",
            f"/api/_action/media/{ID}/upload",
            params={"extension": "svg", "fileName": "ring & seal"},
            content=b"<svg />",
            content_type="image/svg+xml",
        )
    assert result is None
    request = requests[0]
    assert request.content == b"<svg />"
    assert dict(request.url.params) == {"extension": "svg", "fileName": "ring & seal"}
    assert request.headers["Content-Type"] == "image/svg+xml"
    assert request.headers["Content-Length"] == "7"
    assert request.headers["Authorization"] == "Bearer test-token"
    assert request.headers["sw-language-id"] == "2" * 32


def test_binary_request_is_replayed_unchanged_after_token_refresh():
    uploads = []
    tokens = []

    def handler(request):
        if request.url.path == "/api/oauth/token":
            tokens.append(f"token-{len(tokens)}")
            return httpx.Response(200, json={"access_token": tokens[-1]})
        uploads.append(request)
        return httpx.Response(401 if len(uploads) == 1 else 204)

    with client_for(handler, auth=IntegrationAuth("integration", "secret")) as client:
        client.request(
            "POST",
            "/api/_action/example",
            params={"name": "test"},
            content=b"binary",
            content_type="application/octet-stream",
        )
    assert len(tokens) == len(uploads) == 2
    assert uploads[0].content == uploads[1].content == b"binary"
    assert uploads[0].url == uploads[1].url
    assert uploads[0].headers["Content-Type"] == uploads[1].headers["Content-Type"]
    assert uploads[1].headers["Authorization"] == "Bearer token-1"


@pytest.mark.parametrize(
    "arguments",
    [
        {"payload": {}, "content": b"binary"},
        {"content": "not bytes"},
        {"content_type": "image/svg+xml"},
    ],
)
def test_invalid_raw_body_arguments_fail_before_authentication(arguments):
    with client_for(
        lambda _: pytest.fail("No HTTP expected"), auth=IntegrationAuth("integration", "secret")
    ) as client:
        with pytest.raises(MappingError):
            client.request("POST", "/api/_action/example", **arguments)


def test_binary_write_timeouts_are_not_retried():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timeout", request=request)

    with client_for(handler) as client:
        with pytest.raises(TransportError):
            client.request("POST", "/api/_action/example", content=b"binary")
    assert attempts == 1


def test_patch_model_and_context_validation_fail_without_http():
    with client_for(lambda _: pytest.fail("No HTTP expected")) as client:
        with pytest.raises(MappingError):
            client.with_context(RequestContext(language_id="123"))
        with pytest.raises(MappingError):
            client.set(Product).update(ID, client.set(Category).patch().set(Category.name, "A"))
