"""Run with uv run python -m examples.tshirt_collection; no live shop is used."""

import json
from copy import deepcopy
from typing import Any

import httpx

from shopware_admin import AccessToken

from .context import ShopContext
from .models import Product

# Illustrative IDs for the mock shop, not IDs to use against a real installation.
TAX_ID = "a" * 32
CURRENCY_ID = "b" * 32


def euro_price(gross: float, net: float) -> list[dict[str, str | int | float | bool]]:
    return [{"currencyId": CURRENCY_ID, "gross": gross, "net": net, "linked": True}]


class DemoShop:
    """In-memory endpoint subset for this tutorial, not a Shopware emulator."""

    def __init__(self) -> None:
        self.products: dict[str, dict[str, Any]] = {
            "1" * 32: {
                "id": "1" * 32,
                "name": "Green T-shirt",
                "productNumber": "DEMO-TSHIRT-GREEN",
                "stock": 12,
                "taxId": TAX_ID,
                "price": euro_price(23.80, 20.00),
            },
            "2" * 32: {
                "id": "2" * 32,
                "name": "Discontinued T-shirt",
                "productNumber": "DEMO-TSHIRT-OLD",
                "stock": 0,
                "taxId": TAX_ID,
                "price": euro_price(11.90, 10.00),
            },
        }

    def respond(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = json.loads(request.content) if request.content else {}
        if request.method == "POST" and path == "/api/search/product":
            rows = list(self.products.values())
            for predicate in body.get("filter", []):
                field, value = predicate["field"], predicate["value"]
                if predicate["type"] == "contains":
                    rows = [row for row in rows if value in row.get(field, "")]
                elif predicate["type"] == "equals":
                    rows = [row for row in rows if row.get(field) == value]
                else:
                    raise AssertionError(f"Unsupported demo filter: {predicate}")
            for sort in reversed(body.get("sort", [])):
                rows.sort(key=lambda row: row[sort["field"]], reverse=sort["order"] == "DESC")
            total = len(rows)
            size = body.get("limit", 100)
            offset = (body.get("page", 1) - 1) * size
            return httpx.Response(200, json={"data": rows[offset : offset + size], "total": total})
        if request.method == "POST" and path == "/api/product":
            self.products[body["id"]] = deepcopy(body)
            return httpx.Response(204)
        if path.startswith("/api/product/"):
            entity_id = path.rsplit("/", 1)[1]
            if entity_id not in self.products:
                return httpx.Response(404, json={"errors": []})
            if request.method == "GET":
                return httpx.Response(200, json={"data": self.products[entity_id]})
            if request.method == "PATCH":
                self.products[entity_id].update(deepcopy(body))
                return httpx.Response(204)
            if request.method == "DELETE":
                del self.products[entity_id]
                return httpx.Response(204)
        raise AssertionError(f"Unexpected demo request: {request.method} {path}")


def refresh_collection(shop: ShopContext) -> None:
    # Build a query, then execute it through Shopware's search endpoint.
    query = shop.products.where(Product.name.contains("T-shirt")).order_by(Product.name.asc())
    print("Before:")
    for product in query.fetch_page().items:
        print(product.product_number, product.name, product.stock)

    blue = Product(
        name="Blue T-shirt",
        product_number="DEMO-TSHIRT-BLUE",
        stock=20,
        tax_id=TAX_ID,
        price=euro_price(29.75, 25.00),
    )
    blue_id = shop.products.create(blue)

    # We already know the ID, so get it directly instead of searching.
    created = shop.products.get(blue_id)
    assert created is not None
    print("Created:", created.product_number, created.name)

    # Use a unique product number when the ID is not yet known.
    green = shop.products.where(Product.product_number == "DEMO-TSHIRT-GREEN").one()
    patch = shop.products.patch().set(Product.price, euro_price(17.85, 15.00))
    update = shop.products.prepare_update(green.id, patch)
    print("Price patch:", update.json)
    update.execute()
    updated = shop.products.get(green.id)
    assert updated is not None
    assert updated.price == euro_price(17.85, 15.00)
    print("Updated:", updated.product_number, updated.price[0]["gross"])

    old = shop.products.where(Product.product_number == "DEMO-TSHIRT-OLD").one()
    shop.products.delete(old.id)
    assert shop.products.get(old.id) is None
    print("Deleted:", old.product_number)

    print("After:")
    for product in query.fetch_page().items:
        print(product.product_number, product.name, product.stock)


def main() -> None:
    demo = DemoShop()
    with ShopContext(
        "https://shop.example",
        AccessToken("demo"),
        transport=httpx.MockTransport(demo.respond),
    ) as shop:
        refresh_collection(shop)


if __name__ == "__main__":
    main()
