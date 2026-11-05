import json

import httpx
import pytest

from examples.models import Category, Manufacturer, Media, Product
from shopware_admin import (
    AccessToken,
    Client,
    Criteria,
    Entity,
    Field,
    FieldNotLoadedError,
    MappingError,
    Patch,
    QueryError,
    ToOne,
    api_field,
    to_one,
)


class LegacyProduct(Entity):
    __entity__ = "legacy_product"
    __route__ = "legacy-product"
    manufacturer: ToOne[Manufacturer] = to_one("manufacturer")


class ExtendedManufacturer(Manufacturer):
    erp_reference: Field[str | None] = api_field(
        json_path=("customFields", "erp_reference"), default=None
    )


class ExtendedProduct(Entity):
    __entity__ = "extended_product"
    __route__ = "extended-product"
    manufacturer: ToOne[ExtendedManufacturer] = to_one("manufacturer")


def test_dotted_manufacturer_filter_selects_products_with_the_correct_wire_path():
    requests = []
    with Client(
        "https://shop.example",
        AccessToken("test"),
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(200, json={"data": []})
        ),
    ) as client:
        query = (
            client.set(Product)
            .where(Product.manufacturer.name == "Example")
            .load(Product.manufacturer)
        )
        assert requests == []
        query.fetch_page()
    assert requests[0].url.path == "/api/search/product"
    payload = json.loads(requests[0].content)
    assert payload["filter"] == [
        {"type": "equals", "field": "manufacturer.name", "value": "Example"},
    ]
    assert payload["associations"] == {"manufacturer": {}}


def test_nested_dotted_paths_preserve_the_root_entity():
    predicate = Product.manufacturer.media.url.contains("example")
    assert predicate.entity == "product"
    assert predicate.to_payload() == {
        "type": "contains",
        "field": "manufacturer.media.url",
        "value": "example",
    }
    payload = Criteria(Product).where(predicate).load(Product.manufacturer.media).to_payload()
    assert payload["associations"] == {"manufacturer": {"associations": {"media": {}}}}
    assert Manufacturer.media.url.path == "media.url"
    assert Media.url.path == "url"


def test_collection_filter_and_nested_load_filter_are_distinct():
    payload = (
        Criteria(Product)
        .where(Product.categories.name == "Seals")
        .load(Product.categories, criteria=Criteria(Category).where(Category.active == True))
        .to_payload()
    )
    assert payload["filter"] == [{"type": "equals", "field": "categories.name", "value": "Seals"}]
    assert payload["associations"]["categories"]["filter"] == [
        {"type": "equals", "field": "active", "value": True},
    ]


def test_self_referencing_paths_can_be_chained_and_loaded():
    payload = (
        Criteria(Product)
        .where(Product.categories.parent.parent.name == "Seals")
        .load(Product.categories.parent.parent)
        .to_payload()
    )
    assert payload["filter"][0]["field"] == "categories.parent.parent.name"
    assert payload["associations"] == {
        "categories": {"associations": {"parent": {"associations": {"parent": {}}}}},
    }


def test_association_field_named_path_does_not_collide_with_path_metadata():
    payload = (Product.manufacturer.media.path == "media/example.png").to_payload()
    assert payload == {
        "type": "equals",
        "field": "manufacturer.media.path",
        "value": "media/example.png",
    }


def test_association_views_reuse_fields_without_changing_the_declared_model():
    assert Product.manufacturer.name.path == "manufacturer.name"
    assert Product.manufacturer.media.url.path == "manufacturer.media.url"
    assert ExtendedProduct.manufacturer.erp_reference.path == (
        "manufacturer.customFields.erp_reference"
    )
    assert Manufacturer.name.path == "name"
    assert Manufacturer.name.root is Manufacturer
    assert Product.manufacturer.name.root is Product
    assert ExtendedProduct.manufacturer.name.root is ExtendedProduct


def test_single_entity_declarations_support_queries_and_response_values():
    assert (LegacyProduct.manufacturer.name == "Example").to_payload() == {
        "type": "equals",
        "field": "manufacturer.name",
        "value": "Example",
    }
    product = LegacyProduct.from_data({"manufacturer": {"name": "Example"}})
    assert isinstance(product.manufacturer, Manufacturer)
    assert product.manufacturer.name == "Example"


def test_instance_associations_still_return_entities_and_do_not_trigger_http():
    product = Product.from_data(
        {
            "manufacturer": {"name": "Example", "media": {"path": "media/example.png"}},
            "categories": [{"name": "Seals", "active": True}],
        }
    )
    assert isinstance(product.manufacturer, Manufacturer)
    assert product.manufacturer.name == "Example"
    assert isinstance(product.manufacturer.media, Media)
    assert product.manufacturer.media.path == "media/example.png"
    assert isinstance(product.categories[0], Category)
    missing = Product()
    assert missing.manufacturer is None
    with pytest.raises(FieldNotLoadedError):
        _ = missing.categories


def test_unknown_association_members_fail_rather_than_creating_arbitrary_paths():
    with pytest.raises(AttributeError):
        _ = Product.manufacturer.nmae
    with pytest.raises(AttributeError):
        _ = Product.manufacturer.media.unknown


def test_association_fields_cannot_be_used_as_direct_patch_fields():
    with pytest.raises(MappingError):
        Patch(Product).set(Product.manufacturer.name, "Example")


def test_handwritten_related_fields_use_their_declared_json_and_criteria_paths():
    predicate = ExtendedProduct.manufacturer.erp_reference == "ERP-1"
    assert predicate.entity == "extended_product"
    assert predicate.to_payload() == {
        "type": "equals",
        "field": "manufacturer.customFields.erp_reference",
        "value": "ERP-1",
    }
    product = ExtendedProduct.from_data(
        {
            "manufacturer": {"name": "Example", "customFields": {"erp_reference": "ERP-1"}},
        }
    )
    assert product.manufacturer.erp_reference == "ERP-1"


def test_load_requires_an_association_path_from_the_query_root():
    with pytest.raises(QueryError):
        Criteria(Product).load(Manufacturer)
    with pytest.raises(QueryError):
        Criteria(Product).load(Category.parent)


def test_association_views_cannot_be_repository_models():
    with Client("https://shop.example", AccessToken("test")) as client:
        with pytest.raises(MappingError):
            client.set(Product.manufacturer)


def test_presence_uses_the_direct_association_and_hydrates_declared_classes():
    product = Product.from_data({"manufacturer": {"name": "Example"}})
    assert product.is_loaded(Product.manufacturer)
    assert not Product().is_loaded(Product.manufacturer)
    assert type(product.manufacturer) is Manufacturer
    with pytest.raises(MappingError):
        product.is_loaded(Product.manufacturer.media)
    with pytest.raises(MappingError):
        product.is_loaded(Manufacturer)


def test_multiple_associations_to_the_same_model_have_independent_paths():
    assert Category.parent.name.path == "parent.name"
    assert Category.parent.parent.name.path == "parent.parent.name"
    assert Product.categories.parent.name.path == "categories.parent.name"
    assert Category.name.path == "name"


def test_fields_cannot_be_compared_to_association_views():
    with pytest.raises(QueryError):
        _ = Product.name == Product.manufacturer
