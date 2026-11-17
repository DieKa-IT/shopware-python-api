"""Handwritten context extensions remain separate from the generated base."""

from shopware_admin import Query

from .context_base import ShopContextBase
from .models import Product


class ShopContext(ShopContextBase):
    def available_products(self) -> Query[Product]:
        return self.products.where(Product.stock > 0)
