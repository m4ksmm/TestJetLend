from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser

from apps.shop.models import Product


def get_user_by_id(user_id: int) -> AbstractBaseUser:
    user_model = get_user_model()
    return user_model.objects.get(pk=user_id)


def get_products_by_ids(product_ids: list[int]) -> dict[int, Product]:
    return Product.objects.select_related("category").in_bulk(product_ids)
