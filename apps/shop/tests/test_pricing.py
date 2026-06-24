from decimal import Decimal

from django.test import TestCase

from apps.shop.services.pricing import OrderPriceCalculator
from apps.shop.tests.factories import create_category, create_product, create_promo_code


class OrderPriceCalculatorTests(TestCase):
    def test_calculates_order_totals_with_discounted_and_full_price_items(self):
        category = create_category("Pricing")
        discounted_product = create_product(
            name="Discounted",
            category=category,
            price="99.99",
        )
        full_price_product = create_product(
            name="Full price",
            category=category,
            price="50.00",
            is_promo_excluded=True,
        )
        promo_code = create_promo_code(
            code="PRICE10",
            discount_percent="10.00",
            categories=[category],
        )

        result = OrderPriceCalculator.calculate(
            order_items=[
                (discounted_product, 2),
                (full_price_product, 1),
            ],
            promo_code=promo_code,
            discount_rate=Decimal("0.1000"),
        )

        self.assertEqual(result.price, Decimal("249.98"))
        self.assertEqual(result.total, Decimal("229.98"))
        self.assertEqual(result.discount, Decimal("0.0800"))
        self.assertEqual(result.items[0].unit_price, Decimal("99.99"))
        self.assertEqual(result.items[0].total, Decimal("179.98"))
        self.assertEqual(result.items[1].discount, Decimal("0.0000"))
        self.assertEqual(result.items[1].total, Decimal("50.00"))

    def test_rounds_money_half_up(self):
        self.assertEqual(
            OrderPriceCalculator.money(Decimal("10.005")),
            Decimal("10.01"),
        )
