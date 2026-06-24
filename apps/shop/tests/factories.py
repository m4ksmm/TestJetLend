from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.shop.models import Category, Product, PromoCode


def create_user(username: str = "user"):
    user_model = get_user_model()
    return user_model.objects.create_user(username=username, password="password")


def create_category(name: str = "Electronics") -> Category:
    return Category.objects.create(name=name)


def create_product(
    *,
    name: str = "Product",
    category: Category | None = None,
    price: str | Decimal = "100.00",
    is_promo_excluded: bool = False,
) -> Product:
    return Product.objects.create(
        name=name,
        category=category or create_category(),
        price=Decimal(price),
        is_promo_excluded=is_promo_excluded,
    )


def create_promo_code(
    *,
    code: str = "SUMMER2025",
    discount_percent: str | Decimal = "10.00",
    valid_until=None,
    max_uses: int = 10,
    is_active: bool = True,
    categories: list[Category] | None = None,
) -> PromoCode:
    promo_code = PromoCode.objects.create(
        code=code,
        discount_percent=Decimal(discount_percent),
        valid_until=valid_until or timezone.now() + timezone.timedelta(days=7),
        max_uses=max_uses,
        is_active=is_active,
    )
    if categories:
        promo_code.categories.set(categories)
    return promo_code
