from datetime import datetime

import pytest

from examples.models import Category, Manufacturer, Product, ProductBase
from shopware_admin import (
    Entity,
    Field,
    FieldNotLoadedError,
    MappingError,
    ModelRegistry,
    ToOne,
    api_field,
    to_one,
)


class ProductHolder(Entity):
    __entity__ = "holder"
    __route__ = "holder"
    product: ToOne[ProductBase] = to_one("product")


class Event(Entity):
    __entity__ = "event"
    __route__ = "event"
    happened_at: Field[datetime | None] = api_field("happenedAt", default=None)
    tags: Field[list[str]] = api_field("tags", default=None)


def test_typed_values_aliases_and_manual_extensions():
    product = Product.from_data(
        {
            "id": "1" * 32,
            "name": None,
            "stock": 10,
            "productNumber": "ARC-1",
            "customFields": {"erp_reference": "ERP-1", "unknown": 42},
            "newServerField": "kept",
        }
    )
    assert product.name is None
    assert product.stock == 10
    assert product.product_number == "ARC-1"
    assert product.erp_reference == "ERP-1"
    assert product.is_loaded(Product.name)
    assert not product.is_loaded(Product.manufacturer)
    assert product.raw_data["newServerField"] == "kept"
    assert "newServerField" not in product.to_payload()
    assert product.to_payload()["customFields"] == {"erp_reference": "ERP-1"}


def test_missing_null_and_empty_associations_are_distinct():
    missing = Product.from_data({"stock": 0})
    assert missing.name is None
    assert missing.manufacturer is None
    assert not missing.is_loaded(Product.name)
    assert not missing.is_loaded(Product.manufacturer)
    assert missing.to_payload() == {"stock": 0}
    with pytest.raises(FieldNotLoadedError):
        _ = missing.categories
    loaded = Product.from_data({"name": None, "manufacturer": None, "categories": []})
    assert loaded.name is None
    assert loaded.manufacturer is None
    assert loaded.categories == []
    assert loaded.is_loaded(Product.manufacturer)


def test_null_collection_response_is_unloaded_and_empty_array_is_loaded():
    product = Product.from_data({"categories": None})
    assert not product.is_loaded(Product.categories)
    assert product.raw_data["categories"] is None
    with pytest.raises(FieldNotLoadedError):
        _ = product.categories
    empty = Product.from_data({"categories": []})
    assert empty.is_loaded(Product.categories)
    assert empty.categories == []


def test_omitted_constructor_inputs_are_not_inserted_by_reads():
    product = Product()
    assert product.name is None
    assert product.active is None
    assert product.parent_id is None
    assert product.erp_reference is None
    assert product.manufacturer is None
    assert product.to_payload() == {}
    assert not product.is_loaded(Product.name)
    assert not product.is_loaded(Product.manufacturer)
    with pytest.raises(FieldNotLoadedError):
        _ = product.stock
    with pytest.raises(FieldNotLoadedError):
        _ = product.id
    assert product.to_payload() == {}


def test_explicit_constructor_nulls_are_preserved_including_nested_json():
    product = Product(name=None, active=None, erp_reference=None)
    assert product.to_payload() == {
        "name": None,
        "active": None,
        "customFields": {"erp_reference": None},
    }
    assert product.is_loaded(Product.name)
    assert product.is_loaded(Product.active)
    assert product.is_loaded(Product.erp_reference)
    assert not product.is_loaded(Product.parent_id)


def test_assignment_updates_presence_without_inserting_other_defaults():
    product = Product.from_data({"stock": 1})
    assert product.name is None
    assert not product.is_loaded(Product.name)
    product.name = None
    assert product.is_loaded(Product.name)
    assert product.to_payload() == {"stock": 1, "name": None}
    with pytest.raises(MappingError):
        product.id = None
    assert not product.is_loaded(Product.id)


@pytest.mark.parametrize(
    ("custom_fields", "present"),
    [
        ({}, False),
        (None, False),
        ({"erp_reference": None}, True),
    ],
)
def test_nested_response_paths_keep_null_distinct_from_omission(custom_fields, present):
    product = Product.from_data({"customFields": custom_fields})
    assert product.erp_reference is None
    assert product.is_loaded(Product.erp_reference) is present
    assert product.to_payload() == ({"customFields": {"erp_reference": None}} if present else {})


def test_registry_hydrates_handwritten_subclasses_inside_associations():
    holder = ProductHolder.from_data(
        {"product": {"stock": 1, "customFields": {"erp_reference": "ERP-1"}}},
        registry=ModelRegistry([Product]),
    )
    assert isinstance(holder.product, Product)
    assert holder.product.erp_reference == "ERP-1"


def test_wire_association_validation():
    product = Product.from_data(
        {
            "manufacturer": {"id": "2" * 32, "name": "Acme"},
            "categories": [{"id": "3" * 32, "name": "Seals", "active": True}],
        }
    )
    assert isinstance(product.manufacturer, Manufacturer)
    assert isinstance(product.categories[0], Category)
    with pytest.raises(MappingError):
        Product.from_data({"categories": {}})
    with pytest.raises(MappingError):
        Product.from_data({"manufacturer": []})


@pytest.mark.parametrize("value", [True, "10", 10.5, None])
def test_scalar_values_are_not_coerced(value):
    with pytest.raises(MappingError):
        Product(stock=value)
    with pytest.raises(MappingError):
        Product.from_data({"stock": value})


def test_assignment_and_unknown_constructor_arguments_are_validated():
    product = Product(stock=10)
    product.stock = 11
    assert product.stock == 11
    with pytest.raises(MappingError):
        product.stock = "ten"
    with pytest.raises(MappingError):
        Product(typo=10)
    with pytest.raises(MappingError):
        Product(created_at="yesterday")


def test_read_only_values_can_be_read_but_are_never_written():
    product = Product.from_data({"createdAt": "2026-01-01", "name": "A"})
    assert product.created_at == "2026-01-01"
    assert product.to_payload() == {"name": "A"}
    with pytest.raises(MappingError):
        product.created_at = "tomorrow"


def test_unknown_response_fields_are_defensive_copies():
    source = {"stock": 1, "unknown": {"value": 1}}
    product = Product.from_data(source)
    source["unknown"]["value"] = 2
    raw = product.raw_data
    raw["unknown"]["value"] = 3
    assert product.raw_data["unknown"]["value"] == 1


def test_datetime_and_container_round_trip():
    event = Event.from_data({"happenedAt": "2026-10-12T10:00:00Z", "tags": ["a"]})
    assert event.happened_at == datetime.fromisoformat("2026-10-12T10:00:00+00:00")
    assert event.to_payload() == {"happenedAt": "2026-10-12T10:00:00+00:00", "tags": ["a"]}
    with pytest.raises(MappingError):
        Event.from_data({"tags": [1]})


def test_mapping_conflicts_are_reported_at_class_definition():
    with pytest.raises(MappingError, match="Duplicate"):

        class BadProduct(ProductBase):
            another_stock: Field[int] = api_field("stock")

    with pytest.raises(MappingError, match="shadows"):

        class Shadowed(ProductBase):
            stock = 0


def test_model_registry_rejects_sibling_overrides():
    class OtherProduct(ProductBase):
        pass

    registry = ModelRegistry([Product])
    registry.register(ProductBase)
    assert registry.resolve(ProductBase) is Product
    with pytest.raises(MappingError, match="Conflicting"):
        registry.register(OtherProduct)


def test_is_loaded_requires_a_direct_matching_field():
    product = Product(stock=1)
    with pytest.raises(MappingError):
        product.is_loaded(Manufacturer.name)
    with pytest.raises(MappingError):
        product.is_loaded(Product.manufacturer.name)


def test_fields_with_no_default_remain_required_in_the_typed_constructor():
    # An optional constructor argument does not make a nonnullable attribute nullable.
    product = Product()
    with pytest.raises(FieldNotLoadedError):
        _ = product.id

    class Required(Entity):
        count: Field[int] = api_field("count")

    with pytest.raises(MappingError, match="Constructor requires count"):
        Required()
    assert Required(count=1).count == 1
