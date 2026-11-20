import json

import httpx
import pytest

from examples.models import Category, Product, ProductBase
from shopware_admin import AccessToken, Client, Field, MappingError, Patch, api_field

ID = "1" * 32


class ExtendedProduct(Product):
    warehouse: Field[str | None] = api_field(json_path=("customFields", "warehouse"), default=None)


def test_field_assignments_send_one_immediate_request_without_loading_an_entity():
    requests = []
    changes = [Product.stock.set(12), Product.name.set("Updated"), Product.parent_id.set(None)]
    with Client(
        "https://shop.example",
        AccessToken("test"),
        models=[Product],
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(204)
        ),
    ) as client:
        assert requests == []
        assert client.set(Product).update(ID, *changes) is None
        assert len(requests) == 1
    assert requests[0].method == "PATCH"
    assert requests[0].url.path == f"/api/product/{ID}"
    assert json.loads(requests[0].content) == {
        "stock": 12,
        "name": "Updated",
        "parentId": None,
    }


def test_inherited_and_handwritten_fields_merge_nested_payloads():
    requests = []
    assert ExtendedProduct.stock.set(12).model is ExtendedProduct
    with Client(
        "https://shop.example",
        AccessToken("test"),
        models=[ExtendedProduct],
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(204)
        ),
    ) as client:
        client.set(ExtendedProduct).update(
            ID,
            ExtendedProduct.stock.set(12),
            ExtendedProduct.erp_reference.set("ERP-1"),
            ExtendedProduct.warehouse.set("Berlin"),
        )
    assert len(requests) == 1
    assert json.loads(requests[0].content) == {
        "stock": 12,
        "customFields": {"erp_reference": "ERP-1", "warehouse": "Berlin"},
    }


def test_duplicate_assignments_use_the_last_value_without_changing_input_patches():
    first = Product.stock.set(1)
    later = Patch(Product).set(Product.stock, 12).set(Product.name, "Updated")
    with Client("https://shop.example", AccessToken("test"), models=[Product]) as client:
        request = client.set(Product).prepare_update(ID, first, later, Product.name.set(None))
    assert request.json == {"stock": 12, "name": None}
    assert first.to_payload() == {"stock": 1}
    assert later.to_payload() == {"stock": 12, "name": "Updated"}


def test_field_assignments_and_previews_snapshot_mutable_values():
    requests = []
    prices = [{"gross": 10.0}]
    change = Product.price.set(prices)
    prices[0]["gross"] = 20.0
    with Client(
        "https://shop.example",
        AccessToken("test"),
        models=[Product],
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(204)
        ),
    ) as client:
        prepared = client.set(Product).prepare_update(ID, change, Product.name.set(None))
        preview = prepared.json
        preview["price"][0]["gross"] = 30.0
        payload = change.to_payload()
        payload["price"][0]["gross"] = 40.0
        assert requests == []
        prepared.execute()
    assert json.loads(requests[0].content) == {"price": [{"gross": 10.0}], "name": None}
    assert change.to_payload() == {"price": [{"gross": 10.0}]}


@pytest.mark.parametrize(
    "changes",
    [
        (),
        (Patch(Product),),
        (Category.name.set("Other"),),
        (Product.stock.set(12), Category.name.set("Other")),
        (ProductBase.stock.set(12),),
        (ExtendedProduct.stock.set(12),),
        (ExtendedProduct.warehouse.set("Berlin"),),
        (Product.id.set("2" * 32),),
        ({"stock": 12},),
    ],
)
@pytest.mark.parametrize("method", ["update", "prepare_update"])
def test_invalid_update_selections_fail_before_http(changes, method):
    with Client(
        "https://shop.example",
        AccessToken("test"),
        models=[Product],
        transport=httpx.MockTransport(lambda _: pytest.fail("No HTTP expected")),
    ) as client:
        with pytest.raises(MappingError):
            getattr(client.set(Product), method)(ID, *changes)


@pytest.mark.parametrize("value", ["twelve", None, True])
def test_field_assignments_validate_the_declared_value_type(value):
    with pytest.raises(MappingError):
        Product.stock.set(value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (Product.created_at, "today"),
        (Product.manufacturer.name, "Other"),
        (Product.manufacturer.media.path, "image.png"),
        (Product.categories.name, "Other"),
    ],
)
def test_field_assignments_reject_read_only_fields_and_association_traversals(field, value):
    with pytest.raises(MappingError):
        field.set(value)
