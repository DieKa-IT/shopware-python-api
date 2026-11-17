import pytest

from examples.models import Category, Manufacturer, Product
from shopware_admin import Criteria, MappingError, Patch, QueryError


@pytest.mark.parametrize(
    ("expression", "payload"),
    [
        (Product.name == "blub", {"type": "equals", "field": "name", "value": "blub"}),
        (Product.stock >= 10, {"type": "range", "field": "stock", "parameters": {"gte": 10}}),
        (Product.stock > 10, {"type": "range", "field": "stock", "parameters": {"gt": 10}}),
        (Product.stock < 10, {"type": "range", "field": "stock", "parameters": {"lt": 10}}),
        (Product.stock <= 10, {"type": "range", "field": "stock", "parameters": {"lte": 10}}),
        (Product.parent_id.is_null(), {"type": "equals", "field": "parentId", "value": None}),
        (
            Product.id.in_(["1" * 32, "2" * 32]),
            {"type": "equalsAny", "field": "id", "value": ["1" * 32, "2" * 32]},
        ),
        (Product.name.contains("ring"), {"type": "contains", "field": "name", "value": "ring"}),
        (Product.name.startswith("ARC"), {"type": "prefix", "field": "name", "value": "ARC"}),
        (Product.name.endswith("ring"), {"type": "suffix", "field": "name", "value": "ring"}),
        (
            Product.erp_reference == "ERP-1",
            {"type": "equals", "field": "customFields.erp_reference", "value": "ERP-1"},
        ),
    ],
)
def test_filter_compilation(expression, payload):
    assert Criteria(Product).where(expression).to_payload() == {"filter": [payload]}


def test_boolean_composition_is_explicit():
    expression = ((Product.name == "blub") & (Product.stock > 0)) | ~(Product.active == True)
    payload = expression.to_payload()
    assert payload["operator"] == "OR"
    assert payload["queries"][0]["operator"] == "AND"
    assert payload["queries"][1]["type"] == "not"
    assert (Product.name != "blub").to_payload()["type"] == "not"
    with pytest.raises(QueryError):
        bool(expression)
    with pytest.raises(QueryError):
        _ = (Product.stock > 0) and (Product.name == "blub")
    with pytest.raises(QueryError):
        Criteria(Product).where(Product.name is None)


def test_queries_are_immutable_and_snapshot_input_values():
    values = ["one", "two"]
    base = Criteria(Product)
    filtered = base.where(Product.name.in_(values)).limit(10)
    values.append("three")
    assert base.to_payload() == {}
    assert filtered.to_payload()["filter"][0]["value"] == ["one", "two"]
    changed = filtered.to_payload()
    changed["filter"][0]["value"].append("four")
    assert filtered.to_payload()["filter"][0]["value"] == ["one", "two"]


def test_association_root_filter_and_loaded_collection_filter_are_separate():
    criteria = (
        Criteria(Product)
        .where(Product.manufacturer.name == "Acme")
        .load(Product.manufacturer)
        .load(
            Product.categories, criteria=Criteria(Category).where(Category.active == True).limit(5)
        )
        .order_by(Product.name.asc(natural=True), Product.id.desc())
    )
    payload = criteria.to_payload()
    assert payload["filter"][0]["field"] == "manufacturer.name"
    assert payload["associations"]["manufacturer"] == {}
    assert payload["associations"]["categories"] == {
        "filter": [{"type": "equals", "field": "active", "value": True}],
        "limit": 5,
    }
    assert payload["sort"][0] == {"field": "name", "order": "ASC", "naturalSorting": True}


def test_invalid_filters_and_cross_entity_fields_fail_before_http():
    with pytest.raises(QueryError):
        Criteria(Product).where(Manufacturer.name == "Acme")
    with pytest.raises(QueryError):
        _ = (Product.stock > 1) & (Category.active == True)
    with pytest.raises(QueryError):
        _ = Product.stock == Product.stock
    with pytest.raises(QueryError):
        Product.stock.contains("1")
    with pytest.raises(MappingError):
        _ = Product.stock == "ten"
    with pytest.raises(QueryError):
        Product.id.in_([])
    with pytest.raises(QueryError):
        Criteria(Product).load(Product.categories, criteria=Criteria(Manufacturer))
    with pytest.raises(QueryError):
        Criteria(Product).load(Category.parent)
    with pytest.raises(QueryError):
        Criteria(Product).limit(True)


def test_typed_patches_select_only_requested_fields_and_keep_explicit_null():
    patch = Patch(Product).set(Product.name, "A").set(Product.parent_id, None)
    assert patch.to_payload() == {"name": "A", "parentId": None}
    replaced = patch.set(Product.name, "B")
    assert patch.to_payload()["name"] == "A"
    assert replaced.to_payload()["name"] == "B"
    assert Patch(Product).set(Product.erp_reference, "ERP-1").to_payload() == {
        "customFields": {"erp_reference": "ERP-1"},
    }
    with pytest.raises(MappingError):
        Patch(Product).to_payload()
    with pytest.raises(MappingError):
        Patch(Product).set(Product.created_at, "today")
    with pytest.raises(MappingError):
        Patch(Product).set(Product.manufacturer.name, "Acme")


def test_patch_snapshots_mutable_values():
    prices = [{"gross": 10.0}]
    patch = Patch(Product).set(Product.price, prices)
    prices[0]["gross"] = 20.0
    assert patch.to_payload() == {"price": [{"gross": 10.0}]}
