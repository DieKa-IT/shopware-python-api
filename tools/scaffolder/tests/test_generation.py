import importlib
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from shopware_admin import AccessToken, FieldNotLoadedError, MappingError

from shopware_admin_scaffold import ScaffoldError
from shopware_admin_scaffold.generator import render
from shopware_admin_scaffold.selection import select
from shopware_admin_scaffold.writer import apply, inspect


def generate(tmp_path, catalog):
    package = "generated_" + uuid4().hex
    root = tmp_path / package
    selected = select(catalog, ["product"], related=True)
    plan = render(
        catalog,
        selected,
        package,
        "ShopContext",
        entity_overrides={
            "product_manufacturer": {"class_name": "Manufacturer", "set_name": "manufacturers"}
        },
    )
    apply(root, plan)
    return package, root, plan


def test_generated_models_context_null_presence_and_public_associations(
    tmp_path, catalog, monkeypatch
):
    package, root, plan = generate(tmp_path, catalog)
    extension = root / "models/manufacturer.py"
    extension.write_text(
        extension.read_text()
        + '\n    erp_reference: Field[str | None] = api_field("erpReference", default=None)\n'
    )
    extension.write_text("from shopware_admin import Field, api_field\n\n" + extension.read_text())
    monkeypatch.syspath_prepend(str(tmp_path))
    Product = importlib.import_module(f"{package}.models.product").Product
    Category = importlib.import_module(f"{package}.models.category").Category
    Manufacturer = importlib.import_module(f"{package}.models.manufacturer").Manufacturer
    Context = importlib.import_module(f"{package}.context").ShopContext
    with Context("https://shop.example", AccessToken("demo")) as shop:
        assert shop.products.model is Product
        assert shop.manufacturers.model is Manufacturer
        assert Product.manufacturer.erp_reference.path == "manufacturer.erpReference"
        assert (
            Category.parent.products.manufacturer.erp_reference.path
            == "parent.products.manufacturer.erpReference"
        )
        assert Product.erp_sync.product.name.path == "erpSync.product.name"
        product = Product.from_data(
            {
                "manufacturer": {"erpReference": "ERP-1"},
                "categories": [],
                "extensions": {"erpSync": {"status": "ok"}},
                "createdAt": "2026-10-13T08:00:00Z",
            },
            registry=shop.registry,
        )
        assert type(product.manufacturer) is Manufacturer
        assert product.manufacturer.erp_reference == "ERP-1"
        assert product.categories == []
        assert product.erp_sync.status == "ok"
        assert product.created_at.year == 2026
        assert Product().to_payload() == {}
        assert Product(name=None).to_payload() == {"name": None}
        with pytest.raises(FieldNotLoadedError):
            _ = Product().stock
        with pytest.raises(FieldNotLoadedError):
            _ = Product().categories
        with pytest.raises(MappingError, match="read-only"):
            product.created_at = product.created_at
        with pytest.raises(MappingError):
            shop.products.prepare_create(Product())
        request = shop.products.prepare_create(Product(stock=0, product_number="X", price=[]))
        assert request.json["stock"] == 0
        assert len(request.json["id"]) == 32
    before = extension.read_bytes()
    assert inspect(root, plan) == ()
    apply(root, plan, force=True)
    assert extension.read_bytes() == before


def test_every_import_order_in_fresh_interpreters(tmp_path, catalog):
    package, _, _ = generate(tmp_path, catalog)
    environment = {**os.environ, "PYTHONPATH": str(tmp_path)}
    for module in (
        "models.product",
        "models.category",
        "models.manufacturer",
        "_generated.model_bases",
        "context",
    ):
        program = f"""import importlib
importlib.import_module({f"{package}.{module}"!r})
from {package}.models.product import Product
from {package}.models.category import Category
expression = Product.categories.parent.products.product_number
assert expression.path == "categories.parent.products.productNumber"
assert Category.parent.name.path == "parent.name"
"""
        subprocess.run(
            [sys.executable, "-c", program], env=environment, check=True, capture_output=True
        )


def test_generated_consumer_passes_mypy_pyright_and_ruff(tmp_path, catalog):
    package, root, _ = generate(tmp_path, catalog)
    extension = root / "models/manufacturer.py"
    extension.write_text(
        extension.read_text().replace(
            "from .._generated", "from shopware_admin import Field, api_field\n\nfrom .._generated"
        )
        + '\n    erp_reference: Field[str | None] = api_field("erpReference", default=None)\n'
    )
    (root / "typing_contract.py").write_text("""from typing import assert_type

from shopware_admin import FieldExpression, Repository

from .context import ShopContext
from .models.category import Category
from .models.manufacturer import Manufacturer
from .models.product import Product


def contract(shop: ShopContext) -> None:
    assert_type(shop.products, Repository[Product])
    assert_type(shop.manufacturers, Repository[Manufacturer])
    assert_type(Product.manufacturer, type[Manufacturer])
    assert_type(Product.manufacturer.erp_reference, FieldExpression[str | None])
    assert_type(Product.categories, type[Category])
    assert_type(Product.product_number, FieldExpression[str])
    assert_type(Product().categories, list[Category])
    assert_type(Product().manufacturer, Manufacturer | None)
""")
    environment = {**os.environ, "PYTHONPATH": str(tmp_path)}
    commands = [
        [sys.executable, "-m", "mypy", "--strict", str(root)],
        [str(Path(sys.executable).parent / "pyright"), str(root)],
        [str(Path(sys.executable).parent / "ruff"), "check", str(root)],
    ]
    for command in commands:
        result = subprocess.run(command, env=environment, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
    assert package in root.name


def test_force_cannot_adopt_files_or_touch_public_files(tmp_path, catalog):
    root = tmp_path / "shop"
    root.mkdir()
    existing = root / "_generated/model_bases.py"
    existing.parent.mkdir()
    existing.write_text("manual = True\n")
    plan = render(catalog, select(catalog, ["product"]), "shop")
    with pytest.raises(ScaffoldError, match="unowned"):
        apply(root, plan, force=True)
    assert existing.read_text() == "manual = True\n"
    assert not (root / "models").exists()


def test_preflight_force_check_and_name_stability(tmp_path, catalog):
    package, root, plan = generate(tmp_path, catalog)
    source = root / "_generated/model_bases.py"
    source.write_text(source.read_text() + "# Edited\n")
    assert any(change.edited for change in inspect(root, plan))
    with pytest.raises(ScaffoldError, match="--force"):
        apply(root, plan)
    assert source.read_text().endswith("# Edited\n")
    apply(root, plan, force=True)
    assert inspect(root, plan) == ()
    renamed = render(catalog, select(catalog, ["product"], related=True), package, "ShopContext")
    with pytest.raises(ScaffoldError, match="Public class_name changed"):
        apply(root, renamed, force=True)
    reduced = render(catalog, select(catalog, ["product"]), package, "ShopContext")
    with pytest.raises(ScaffoldError, match="Removed entity"):
        apply(root, reduced, force=True)


def test_symlink_destinations_are_rejected_before_any_write(tmp_path, catalog):
    root = tmp_path / "shop"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "models").symlink_to(outside, target_is_directory=True)
    plan = render(catalog, select(catalog, ["product"]), "shop")
    with pytest.raises(ScaffoldError, match="symlink"):
        apply(root, plan)
    assert list(outside.iterdir()) == []
    assert not (root / "__init__.py").exists()


def test_invalid_output_parents_fail_before_writing(tmp_path, catalog):
    root = tmp_path / "shop"
    root.mkdir()
    (root / "models").write_text("not a directory")
    plan = render(catalog, select(catalog, ["product"]), "shop")
    with pytest.raises(ScaffoldError, match="parent is not a directory"):
        apply(root, plan)
    assert not (root / "_generated").exists()
    assert not (root / "__init__.py").exists()
