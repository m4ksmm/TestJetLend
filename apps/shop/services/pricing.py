from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from apps.shop.models import Product, PromoCode
from apps.shop.services.promo_service import PromoCodeService

MONEY_QUANT = Decimal("0.01")
DISCOUNT_QUANT = Decimal("0.0001")
ZERO_MONEY = Decimal("0.00")
ZERO_DISCOUNT = Decimal("0.0000")


@dataclass(frozen=True)
class OrderLinePrice:
    product: Product
    quantity: int
    unit_price: Decimal
    line_price: Decimal
    discount: Decimal
    total: Decimal


@dataclass(frozen=True)
class OrderPrice:
    items: list[OrderLinePrice]
    price: Decimal
    discount: Decimal
    total: Decimal


class OrderPriceCalculator:
    @classmethod
    def calculate(
        cls,
        *,
        order_items: list[tuple[Product, int]],
        promo_code: PromoCode | None,
        discount_rate: Decimal = ZERO_DISCOUNT,
    ) -> OrderPrice:
        calculated_items = []
        order_price = ZERO_MONEY
        order_total = ZERO_MONEY

        for product, quantity in order_items:
            unit_price = cls.money(product.price)
            line_price = cls.money(unit_price * quantity)
            item_discount = cls.get_item_discount(
                product=product,
                promo_code=promo_code,
                discount_rate=discount_rate,
            )
            item_total = cls.apply_discount(line_price, item_discount)

            calculated_items.append(
                OrderLinePrice(
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_price=line_price,
                    discount=item_discount,
                    total=item_total,
                )
            )
            order_price += line_price
            order_total += item_total

        return OrderPrice(
            items=calculated_items,
            price=cls.money(order_price),
            discount=cls.calculate_discount(order_price, order_total),
            total=cls.money(order_total),
        )

    @staticmethod
    def get_item_discount(
        *,
        product: Product,
        promo_code: PromoCode | None,
        discount_rate: Decimal,
    ) -> Decimal:
        if not promo_code:
            return ZERO_DISCOUNT

        if PromoCodeService.can_apply_to_product(promo_code, product):
            return discount_rate

        return ZERO_DISCOUNT

    @staticmethod
    def money(value: Decimal) -> Decimal:
        return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

    @classmethod
    def apply_discount(cls, price: Decimal, discount: Decimal) -> Decimal:
        return cls.money(price * (Decimal("1") - discount))

    @staticmethod
    def calculate_discount(price: Decimal, total: Decimal) -> Decimal:
        if price == ZERO_MONEY:
            return ZERO_DISCOUNT
        return ((price - total) / price).quantize(DISCOUNT_QUANT)
