from collections.abc import Iterable
from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction

from apps.shop.exceptions import OrderValidationError, PromoCodeValidationError
from apps.shop.models import Order, OrderItem, Product, PromoCodeUsage
from apps.shop.selectors import get_products_by_ids, get_user_by_id
from apps.shop.services.pricing import ZERO_DISCOUNT, OrderPriceCalculator
from apps.shop.services.promo_service import PromoCodeService


@dataclass(frozen=True)
class OrderGoodInput:
    good_id: int
    quantity: int


class OrderService:
    @classmethod
    def create_order(
        cls,
        *,
        user_id: int,
        goods: Iterable[dict],
        promo_code: str | None = None,
    ) -> Order:
        normalized_goods = cls._normalize_goods(goods)

        with transaction.atomic():
            user = cls._get_user(user_id)
            products = cls._get_products(normalized_goods)

            locked_promo_code = None
            discount_rate = ZERO_DISCOUNT
            if promo_code:
                locked_promo_code = PromoCodeService.get_locked_promo_code(promo_code)
                PromoCodeService.validate_for_user(locked_promo_code, user.id)
                discount_rate = PromoCodeService.get_discount_rate(locked_promo_code)

            order_price = OrderPriceCalculator.calculate(
                order_items=[
                    (products[item.good_id], item.quantity) for item in normalized_goods
                ],
                promo_code=locked_promo_code,
                discount_rate=discount_rate,
            )
            order = Order.objects.create(
                user=user,
                promo_code=locked_promo_code,
                price=order_price.price,
                discount=order_price.discount,
                total=order_price.total,
            )

            OrderItem.objects.bulk_create(
                OrderItem(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.unit_price,
                    discount=item.discount,
                    total=item.total,
                )
                for item in order_price.items
            )

            if locked_promo_code:
                try:
                    PromoCodeUsage.objects.create(
                        user=user,
                        promo_code=locked_promo_code,
                        order=order,
                    )
                except IntegrityError as exc:
                    raise PromoCodeValidationError(
                        "User has already used this promo code."
                    ) from exc

            return (
                Order.objects.select_related("user", "promo_code")
                .prefetch_related("items__product")
                .get(pk=order.pk)
            )

    @classmethod
    def _normalize_goods(cls, goods: Iterable[dict]) -> list[OrderGoodInput]:
        normalized = [
            OrderGoodInput(good_id=item["good_id"], quantity=item["quantity"])
            for item in goods
        ]
        product_ids = [item.good_id for item in normalized]
        if len(product_ids) != len(set(product_ids)):
            raise OrderValidationError(
                "Duplicate goods are not allowed.", field="goods"
            )
        return normalized

    @classmethod
    def _get_user(cls, user_id: int):
        try:
            return get_user_by_id(user_id)
        except ObjectDoesNotExist as exc:
            raise OrderValidationError("User does not exist.", field="user_id") from exc

    @classmethod
    def _get_products(cls, goods: list[OrderGoodInput]) -> dict[int, Product]:
        product_ids = [item.good_id for item in goods]
        products = get_products_by_ids(product_ids)
        missing_ids = sorted(set(product_ids) - set(products))
        if missing_ids:
            raise OrderValidationError(
                f"Products do not exist: {', '.join(map(str, missing_ids))}.",
                field="goods",
            )
        return products
