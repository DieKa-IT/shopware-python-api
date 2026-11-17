"""Run with uv run python -m examples.demo. No network or credentials required."""

import json

import httpx

from shopware_admin import AccessToken, CountMode, Criteria

from .context import ShopContext
from .models import Category, Product


def respond(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "total": 1,
            "data": [
                {
                    "id": "1" * 32,
                    "name": "O-ring 20x3",
                    "productNumber": "ARC-4711",
                    "stock": 12,
                    "customFields": {"erp_reference": "ERP-4711"},
                    "manufacturer": {"id": "2" * 32, "name": "Example"},
                    "categories": [],
                }
            ],
            "aggregations": {},
        },
    )


def main() -> None:
    with ShopContext(
        "https://shop.example",
        AccessToken("demo"),
        transport=httpx.MockTransport(respond),
    ) as shop:
        query = (
            shop.products.where(Product.name.contains("ring"), Product.stock > 0)
            .where(Product.manufacturer.name == "Example")
            .order_by(Product.name.asc(), Product.id.asc())
            .load(Product.manufacturer)
            .load(Product.categories, criteria=Criteria(Category).where(Category.active == True))
        )
        request = query.prepare(size=100, count=CountMode.EXACT)
        print(f"{request.method} {request.path}")
        print(json.dumps(request.json, indent=2))
        result = request.execute()
        for product in result.items:
            print(product.name, product.stock, product.erp_reference)

        patch = shop.products.patch().set(Product.name, "Updated name").set(Product.parent_id, None)
        print("Patch preview:", shop.products.prepare_update("1" * 32, patch).json)


if __name__ == "__main__":
    main()
