"""Illustrate a future generated context referencing the public model classes."""

from shopware_admin import Context, entity_set

from .models import Category, Manufacturer, Media, Product


class ShopContextBase(Context):
    products = entity_set(Product)
    categories = entity_set(Category)
    manufacturers = entity_set(Manufacturer)
    media = entity_set(Media)
