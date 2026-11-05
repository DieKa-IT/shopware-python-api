from copy import deepcopy

import pytest

from shopware_admin_scaffold import ScaffoldError
from shopware_admin_scaffold.catalog import Catalog, SchemaResolver
from shopware_admin_scaffold.generator import render
from shopware_admin_scaffold.selection import select


def test_routes_flat_fields_input_requirements_and_wire_types(catalog):
    product = select(catalog, ["Product"])[0]
    fields = {field.wire_name: field for field in product.fields}
    assert product.route == "product"
    assert "internalSecret" not in fields
    assert "data" not in fields
    assert fields["stock"].value_type == "int"
    assert fields["stock"].required_on_create
    assert not fields["active"].nullable
    assert not fields["active"].required_on_create
    assert fields["name"].nullable
    assert not fields["id"].nullable
    assert not fields["id"].required_on_create
    assert fields["createdAt"].value_type == "datetime"
    assert not fields["createdAt"].writable
    assert fields["price"].value_type == "list[dict[str, Any]]"
    assert fields["erpSync"].json_path == ("extensions", "erpSync")


def test_selected_related_entities_expand_only_once(catalog):
    chosen = select(catalog, ["product", "Product"], related=True)
    assert [entity.name for entity in chosen] == [
        "category",
        "dieka_erp_product_sync",
        "product",
        "product_manufacturer",
    ]
    plan = render(catalog, chosen, "shop", "ShopContext")
    assert any("media" in notice and "not selected" in notice for notice in plan.diagnostics)


def test_all_and_unsupported_keys_are_explicit(catalog):
    with pytest.raises(ScaffoldError, match="conventional UUID"):
        select(catalog, [], all_entities=True)
    with pytest.raises(ScaffoldError, match="either"):
        select(catalog, [], all_entities=False)
    with pytest.raises(ScaffoldError, match="missing or ambiguous"):
        select(catalog, ["nothing"])


def test_user_scope_write_protection_and_explicit_nonnullable(bundle):
    dal = deepcopy(bundle.dal)
    dal["product"]["properties"]["stock"]["flags"]["write_protected"] = [["user", "system"]]
    dal["product"]["properties"]["active"]["flags"]["write_protected"] = [[]]
    fields = {
        f.wire_name: f for f in select(Catalog.parse(bundle.openapi, dal), ["product"])[0].fields
    }
    assert fields["stock"].writable
    assert not fields["active"].writable


def test_flat_model_reference_beats_operation_name_and_preserves_exact_route(bundle):
    openapi = deepcopy(bundle.openapi)
    endpoint = openapi["paths"].pop("/product")
    endpoint["get"]["operationId"] = "listPluginProducts"
    openapi["paths"]["/api/special-products"] = endpoint
    chosen = select(Catalog.parse(openapi, bundle.dal), ["product"])
    assert chosen[0].route == "special-products"


def test_ambiguous_entities_references_and_compositions_fail(bundle):
    openapi = deepcopy(bundle.openapi)
    openapi["paths"]["/alternate"] = openapi["paths"]["/product"]
    with pytest.raises(ScaffoldError, match="Multiple OpenAPI routes"):
        Catalog.parse(openapi, bundle.dal)
    resolver = SchemaResolver(bundle.openapi)
    with pytest.raises(ScaffoldError, match="Unsupported schema reference"):
        resolver.resolve({"$ref": "https://example.com/schema.json"})
    with pytest.raises(ScaffoldError, match="Conflicting allOf"):
        resolver.resolve({"allOf": [{"type": "string"}, {"type": "integer"}]})


def test_endpoints_without_exposed_dal_metadata_are_omitted_with_notice(bundle):
    dal = deepcopy(bundle.dal)
    del dal["product_manufacturer"]
    catalog = Catalog.parse(bundle.openapi, dal)
    assert "product_manufacturer" not in {entity.name for entity in catalog.entities}
    assert select(catalog, ["product"])[0].name == "product"
    assert any("no exposed DAL metadata" in notice for notice in catalog.diagnostics)


def test_explicit_entity_identity_without_dal_metadata_still_fails(bundle):
    openapi = deepcopy(bundle.openapi)
    openapi["paths"]["/product"]["get"]["x-entity-name"] = "missing_product"
    with pytest.raises(ScaffoldError, match="ambiguous or missing DAL entity"):
        Catalog.parse(openapi, bundle.dal)


def test_unknown_shapes_and_null_unions_are_not_silently_dropped(bundle):
    openapi = deepcopy(bundle.openapi)
    fields = openapi["components"]["schemas"]["Product"]["allOf"][1]["properties"]
    fields["name"] = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    fields["active"] = {}
    catalog = Catalog.parse(openapi, bundle.dal)
    fields = {f.wire_name: f for f in select(catalog, ["product"])[0].fields}
    assert fields["name"].value_type == "str"
    assert fields["name"].nullable
    assert fields["active"].value_type == "Any"
    assert any("active" in notice and "unknown" in notice for notice in catalog.diagnostics)


def test_naming_overrides_collisions_and_unknown_options(catalog):
    product = select(catalog, ["product"])
    with pytest.raises(ScaffoldError, match="reserved"):
        render(
            catalog, product, "shop", field_overrides={"product": {"name": {"name": "raw_data"}}}
        )
    with pytest.raises(ScaffoldError, match="conflicting Python field"):
        render(catalog, product, "shop", field_overrides={"product": {"name": {"name": "stock"}}})
    with pytest.raises(ScaffoldError, match="unknown fields"):
        render(
            catalog, product, "shop", field_overrides={"product": {"wrong": {"nullable": False}}}
        )
    with pytest.raises(ScaffoldError, match="Invalid or reserved"):
        render(catalog, product, "shop.bad-name")
    with pytest.raises(ScaffoldError, match="boolean"):
        render(
            catalog, product, "shop", field_overrides={"product": {"stock": {"nullable": "yes"}}}
        )


def test_php_empty_flags_and_malformed_types_have_explicit_errors(bundle):
    dal = deepcopy(bundle.dal)
    dal["product"]["properties"]["manufacturerId"]["flags"] = []
    Catalog.parse(bundle.openapi, dal)
    openapi = deepcopy(bundle.openapi)
    openapi["components"]["schemas"]["Product"]["allOf"][1]["required"] = "stock"
    with pytest.raises(ScaffoldError, match="JSON array"):
        Catalog.parse(openapi, dal)
    openapi = deepcopy(bundle.openapi)
    openapi["components"]["schemas"]["Product"]["allOf"][1]["properties"]["stock"] = {
        "type": "string"
    }
    with pytest.raises(ScaffoldError, match="conflicting OpenAPI/DAL"):
        Catalog.parse(openapi, dal)


def test_nonnullable_wire_id_and_standard_version_keys(bundle):
    dal = deepcopy(bundle.dal)
    dal["product"]["properties"]["versionId"] = {"type": "uuid", "flags": {"primary_key": True}}
    assert select(Catalog.parse(bundle.openapi, dal), ["product"])[0].unsupported is None
    dal["product"]["properties"]["otherId"] = {"type": "uuid", "flags": {"primary_key": True}}
    with pytest.raises(ScaffoldError, match="composite primary"):
        select(Catalog.parse(bundle.openapi, dal), ["product"])
    openapi = deepcopy(bundle.openapi)
    openapi["components"]["schemas"]["EntityId"]["properties"]["id"]["nullable"] = True
    with pytest.raises(ScaffoldError, match="nonnullable"):
        select(Catalog.parse(openapi, bundle.dal), ["product"])
