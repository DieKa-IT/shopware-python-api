"""Both mypy and Pyright check this consumer-facing contract."""

from typing import assert_type

from examples.context import ShopContext
from examples.models import (
    Category,
    Manufacturer,
    Media,
    Product,
)
from shopware_admin import (
    AccessToken,
    Client,
    Context,
    Criteria,
    Entity,
    EntitySet,
    Field,
    FieldExpression,
    Patch,
    Predicate,
    PreparedRequest,
    Query,
    Repository,
    RequestContext,
    SearchResult,
    ToMany,
    ToOne,
    api_field,
    entity_set,
    to_many,
    to_one,
)


class ConstructorInputs(Entity):
    count: Field[int] = api_field("count")
    note: Field[str | None] = api_field("note", default=None)


class LegacyAssociations(Entity):
    manufacturer: ToOne[Manufacturer] = to_one("manufacturer")
    categories: ToMany[Category] = to_many("categories")


class ExtendedManufacturer(Manufacturer):
    erp_reference: Field[str | None] = api_field("erpReference", default=None)


class ExtendedProduct(Entity):
    manufacturer: ToOne[ExtendedManufacturer] = to_one("manufacturer")


class ExtendedShopContext(ShopContext):
    erp_manufacturers = entity_set(ExtendedManufacturer)


def context_contract(shop: ShopContext, extended: ExtendedShopContext) -> None:
    assert_type(ShopContext.products, EntitySet[Product])
    assert_type(shop.products, Repository[Product])
    assert_type(shop.products.where(Product.stock > 0), Query[Product])
    assert_type(shop.products.search().fetch_page(), SearchResult[Product])
    assert_type(shop.products.get("1" * 32), Product | None)
    assert_type(shop.products.patch(), Patch[Product])
    assert_type(shop.available_products(), Query[Product])
    localized = shop.with_context(RequestContext(language_id="2" * 32))
    assert_type(localized, ShopContext)
    assert_type(localized.products, Repository[Product])
    assert_type(extended.erp_manufacturers, Repository[ExtendedManufacturer])
    assert_type(extended.with_context(RequestContext()), ExtendedShopContext)
    with shop as entered:
        assert_type(entered, ShopContext)
        assert_type(entered.products, Repository[Product])
    with extended.with_context(RequestContext()) as entered_extended:
        assert_type(entered_extended, ExtendedShopContext)
    assert_type(Context("https://shop.example", AccessToken("demo")), Context)


def contract(client: Client) -> None:
    assert_type(Product().name, str | None)
    assert_type(Product(name=None).name, str | None)
    assert_type(Product().id, str)
    assert_type(ConstructorInputs(count=1).count, int)
    assert_type(ConstructorInputs(count=1, note=None).note, str | None)
    product = Product(name="O-ring", stock=10, erp_reference="ERP-4711")
    assert_type(product.name, str | None)
    assert_type(product.stock, int)
    assert_type(product.erp_reference, str | None)
    assert_type(product.manufacturer, Manufacturer | None)
    assert_type(product.categories, list[Category])
    assert_type(Product.stock, FieldExpression[int])
    assert_type(Product.name, FieldExpression[str | None])
    assert_type(Product.manufacturer, type[Manufacturer])
    assert_type(Product.manufacturer.name, FieldExpression[str | None])
    assert_type(Product.manufacturer.media, type[Media])
    assert_type(Product.manufacturer.media.url, FieldExpression[str | None])
    assert_type(Product.manufacturer.media.path, FieldExpression[str])
    assert_type(Product.categories, type[Category])
    assert_type(Product.categories.name, FieldExpression[str | None])
    assert_type(Product.categories.parent.name, FieldExpression[str | None])
    assert_type(Product.manufacturer.name == "Example", Predicate)
    assert_type(LegacyAssociations.manufacturer, type[Manufacturer])
    assert_type(LegacyAssociations.categories, type[Category])
    assert_type(LegacyAssociations().manufacturer, Manufacturer | None)
    assert_type(ExtendedProduct.manufacturer.erp_reference, FieldExpression[str | None])
    assert_type(ExtendedProduct().manufacturer, ExtendedManufacturer | None)
    assert_type(Product.stock > 1, Predicate)
    assert_type(Product.stock.eq(1), Predicate)
    assert_type((Product.stock > 0) & (Product.name == "blub"), Predicate)
    repository = client.set(Product)
    assert_type(repository, Repository[Product])
    query = repository.where(Product.manufacturer.name == "Example", Product.stock > 0).load(
        Product.categories, criteria=Criteria(Category).where(Category.active == True)
    )
    assert_type(query, Query[Product])
    assert_type(query.load(Product.manufacturer.media, criteria=Criteria(Media)), Query[Product])
    assert_type(query.prepare(), PreparedRequest[SearchResult[Product]])
    assert_type(query.fetch_page(), SearchResult[Product])
    assert_type(query.first(), Product | None)
    assert_type(query.one(), Product)
    assert_type(repository.get("1" * 32), Product | None)
    patch = repository.patch().set(Product.stock, 10).set(Product.name, None)
    assert_type(patch, Patch[Product])


def rejected_inputs() -> None:
    # Verify typed constructor, assignments, comparisons, and patch values reject bad types.
    product = Product(stock="ten")  # type: ignore[arg-type]
    Product(stock=None)  # type: ignore[arg-type]
    ConstructorInputs()  # type: ignore[call-arg]
    product.stock = "ten"  # type: ignore[assignment]
    product.id = None  # type: ignore[assignment]
    Product.stock.eq("ten")  # type: ignore[arg-type]
    _ = Product.stock > "ten"  # type: ignore[operator]
    Patch(Product).set(Product.stock, "ten")  # type: ignore[misc]
    _ = Product.manufacturer.nmae  # type: ignore[attr-defined]
    Product.manufacturer.name.eq(123)  # type: ignore[arg-type]
    Product.categories.active.eq("yes")  # type: ignore[arg-type]
    Patch(Product).set(Product.manufacturer.name, 123)  # type: ignore[misc]
    ExtendedProduct.manufacturer.erp_reference.eq(123)  # type: ignore[arg-type]


def rejected_context_inputs(shop: ShopContext) -> None:
    _ = shop.produtcs  # type: ignore[attr-defined]
    shop.products = shop.products  # type: ignore[assignment]
    shop.products.create(Category())  # type: ignore[arg-type]
    shop.products.patch().set(Product.stock, "ten")  # type: ignore[misc]
