import json

import httpx
import pytest

from examples.context import ShopContext
from examples.models import Category, Product, ProductBase
from shopware_admin import (
    AccessToken,
    Context,
    Entity,
    Field,
    MappingError,
    RequestContext,
    ToOne,
    api_field,
    entity_set,
    to_one,
)


class ProductHolder(Entity):
    __entity__ = "holder"
    __route__ = "holder"
    product: ToOne[ProductBase] = to_one("product")


class HolderContext(ShopContext):
    holders = entity_set(ProductHolder)


class OtherProduct(ProductBase):
    marker: Field[str | None] = api_field("marker", default=None)


def test_context_registers_all_public_models_before_any_set_is_accessed():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": [{"product": {"customFields": {"erp_reference": "ERP-1"}}}]},
        )

    with HolderContext(
        "https://shop.example", AccessToken("demo"), transport=httpx.MockTransport(handler)
    ) as shop:
        query = shop.holders.search()
        prepared = query.prepare()
        assert requests == []
        holder = prepared.execute().items[0]
        assert type(holder.product) is Product
        assert holder.product.erp_reference == "ERP-1"
        assert shop.products.model is Product
        assert shop.categories.model is Category
    assert requests[0].url.path == "/api/search/holder"


def test_named_sets_support_queries_and_explicit_writes():
    requests = []
    with ShopContext(
        "https://shop.example",
        AccessToken("demo"),
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(204)
        ),
    ) as shop:
        prepared = shop.available_products().prepare()
        assert prepared.path == "/api/search/product"
        assert prepared.json["filter"][0]["parameters"] == {"gt": 0}
        patch = shop.products.patch().set(Product.erp_reference, "ERP-2")
        update = shop.products.prepare_update("1" * 32, patch)
        assert requests == []
        update.execute()
    assert requests[0].method == "PATCH"
    assert json.loads(requests[0].content) == {"customFields": {"erp_reference": "ERP-2"}}


def test_localized_views_preserve_subclass_state_and_bind_sets_to_the_view():
    class CustomContext(ShopContext):
        def __init__(self, *args, label, **kwargs):
            super().__init__(*args, **kwargs)
            self.label = label

    requests = []
    with CustomContext(
        "https://shop.example",
        AccessToken("demo"),
        label="ERP",
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(200, json={"data": []})
        ),
    ) as shop:
        with shop.with_context(RequestContext(language_id="2" * 32)) as localized:
            assert type(localized) is CustomContext
            assert localized.label == "ERP"
            assert localized.registry is shop.registry
            assert localized._connection is shop._connection
            assert localized.products.client is localized
            localized.available_products().fetch_page()
        assert not shop._connection.http.is_closed
        shop.products.search().fetch_page()
    assert shop._connection.http.is_closed
    assert requests[0].headers["sw-language-id"] == "2" * 32
    assert "sw-language-id" not in requests[1].headers


def test_separate_contexts_do_not_share_repository_connections():
    with (
        ShopContext(
            "https://first.example",
            AccessToken("a"),
            transport=httpx.MockTransport(lambda _: pytest.fail("No HTTP expected")),
        ) as first,
        ShopContext(
            "https://second.example",
            AccessToken("b"),
            transport=httpx.MockTransport(lambda _: pytest.fail("No HTTP expected")),
        ) as second,
    ):
        assert first.products.client is first
        assert second.products.client is second
        assert first._connection is not second._connection
        with pytest.raises(AttributeError, match="read-only"):
            first.products = second.products


def test_inherited_declarations_follow_python_override_and_mro_rules():
    class OtherContext(Context):
        products = entity_set(OtherProduct)

    class OverrideContext(ShopContext):
        products = entity_set(OtherProduct)

    class CombinedContext(OtherContext, ShopContext):
        pass

    for context_type in (OverrideContext, CombinedContext):
        with context_type("https://shop.example", AccessToken("demo")) as shop:
            assert shop.products.model is OtherProduct
            assert shop.categories.model is Category
            assert shop.registry.resolve(ProductBase) is OtherProduct


def test_shadowed_declarations_are_not_registered():
    class HiddenContext(ShopContext):
        products = None

    with HiddenContext("https://shop.example", AccessToken("demo")) as shop:
        assert shop.products is None
        assert shop.registry.resolve(ProductBase) is ProductBase


def test_explicit_models_can_register_additional_public_subclasses():
    with ShopContext("https://shop.example", AccessToken("demo"), models=[ProductHolder]) as shop:
        assert shop.set(ProductHolder).model is ProductHolder


def test_conflicting_declarations_fail_before_a_connection_is_opened(monkeypatch):
    class ConflictingContext(ShopContext):
        other_products = entity_set(OtherProduct)

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: pytest.fail("No connection expected"))
    with pytest.raises(MappingError, match="Conflicting public models"):
        ConflictingContext("https://shop.example", AccessToken("demo"))


def test_invalid_declarations_fail_explicitly():
    with pytest.raises(MappingError, match="Entity model"):
        entity_set(str)
    with pytest.raises(MappingError, match="metadata"):

        class InvalidContext(Context):
            entities = entity_set(Entity)

        InvalidContext("https://shop.example", AccessToken("demo"))
    with pytest.raises(MappingError, match="conflicts with the client API"):

        class ReservedContext(Context):
            set = entity_set(Product)
