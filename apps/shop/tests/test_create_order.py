from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.shop.exceptions import PromoCodeValidationError
from apps.shop.models import Order, PromoCode, PromoCodeUsage
from apps.shop.services.order_service import OrderService
from apps.shop.services.promo_service import PromoCodeService
from apps.shop.tests.factories import (
    create_category,
    create_product,
    create_promo_code,
    create_user,
)


class CreateOrderAPITests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user("alice")
        self.category = create_category("Books")
        self.product = create_product(
            name="Clean Architecture",
            category=self.category,
            price="100.00",
        )

    def post_order(self, payload: dict):
        return self.client.post("/api/orders/", payload, format="json")

    def test_create_order_without_promo_code(self):
        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": self.product.id, "quantity": 2}],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["price"], "200.00")
        self.assertEqual(response.data["discount"], "0.0000")
        self.assertEqual(response.data["total"], "200.00")
        self.assertEqual(response.data["goods"][0]["price"], "100.00")
        self.assertEqual(response.data["goods"][0]["total"], "200.00")
        self.assertEqual(PromoCodeUsage.objects.count(), 0)

    def test_create_order_with_valid_promo_code(self):
        create_promo_code(code="SUMMER2025", categories=[self.category])

        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": self.product.id, "quantity": 2}],
                "promo_code": "SUMMER2025",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["price"], "200.00")
        self.assertEqual(response.data["discount"], "0.1000")
        self.assertEqual(response.data["total"], "180.00")
        self.assertEqual(response.data["goods"][0]["discount"], "0.1000")
        self.assertEqual(response.data["goods"][0]["total"], "180.00")
        self.assertEqual(PromoCodeUsage.objects.count(), 1)

    def test_promo_code_does_not_exist(self):
        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": self.product.id, "quantity": 1}],
                "promo_code": "MISSING",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"promo_code": ["Promo code does not exist."]})
        self.assertEqual(Order.objects.count(), 0)

    def test_expired_promo_code(self):
        create_promo_code(
            code="OLD",
            valid_until=timezone.now() - timezone.timedelta(days=1),
            categories=[self.category],
        )

        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": self.product.id, "quantity": 1}],
                "promo_code": "OLD",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"promo_code": ["Promo code has expired."]})
        self.assertEqual(Order.objects.count(), 0)

    def test_inactive_promo_code(self):
        create_promo_code(code="OFF", is_active=False, categories=[self.category])

        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": self.product.id, "quantity": 1}],
                "promo_code": "OFF",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"promo_code": ["Promo code is not active."]})
        self.assertEqual(Order.objects.count(), 0)

    def test_promo_code_max_uses_exceeded(self):
        promo_code = create_promo_code(
            code="ONE", max_uses=1, categories=[self.category]
        )
        another_user = create_user("bob")
        OrderService.create_order(
            user_id=another_user.id,
            goods=[{"good_id": self.product.id, "quantity": 1}],
            promo_code=promo_code.code,
        )

        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": self.product.id, "quantity": 1}],
                "promo_code": "ONE",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {"promo_code": ["Promo code usage limit has been reached."]},
        )

    def test_user_cannot_reuse_same_promo_code(self):
        create_promo_code(code="ONCE", max_uses=5, categories=[self.category])
        payload = {
            "user_id": self.user.id,
            "goods": [{"good_id": self.product.id, "quantity": 1}],
            "promo_code": "ONCE",
        }

        first_response = self.post_order(payload)
        second_response = self.post_order(payload)

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            second_response.data,
            {"promo_code": ["User has already used this promo code."]},
        )

    def test_promo_code_applies_only_to_allowed_category(self):
        allowed_category = create_category("Allowed")
        restricted_promo = create_promo_code(
            code="BOOKS", categories=[allowed_category]
        )

        self.assertFalse(
            PromoCodeService.can_apply_to_product(restricted_promo, self.product)
        )

        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": self.product.id, "quantity": 1}],
                "promo_code": "BOOKS",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["discount"], "0.0000")
        self.assertEqual(response.data["total"], "100.00")
        self.assertEqual(response.data["goods"][0]["discount"], "0.0000")

    def test_promo_code_is_not_applied_to_excluded_product(self):
        excluded_product = create_product(
            name="No promo",
            category=self.category,
            price="100.00",
            is_promo_excluded=True,
        )
        create_promo_code(code="SAVE", categories=[self.category])

        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": excluded_product.id, "quantity": 1}],
                "promo_code": "SAVE",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["discount"], "0.0000")
        self.assertEqual(response.data["goods"][0]["discount"], "0.0000")
        self.assertEqual(response.data["total"], "100.00")

    def test_invalid_quantity(self):
        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": self.product.id, "quantity": 0}],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("goods", response.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_product_does_not_exist(self):
        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": 999999, "quantity": 1}],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"goods": ["Products do not exist: 999999."]})
        self.assertEqual(Order.objects.count(), 0)

    def test_user_does_not_exist(self):
        response = self.post_order(
            {
                "user_id": 999999,
                "goods": [{"good_id": self.product.id, "quantity": 1}],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"user_id": ["User does not exist."]})
        self.assertEqual(Order.objects.count(), 0)

    def test_empty_goods_list(self):
        response = self.post_order({"user_id": self.user.id, "goods": []})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("goods", response.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_mixed_order_partially_discounted(self):
        allowed_product = self.product
        excluded_product = create_product(
            name="Gift card",
            category=self.category,
            price="50.00",
            is_promo_excluded=True,
        )
        another_category = create_category("Games")
        another_product = create_product(
            name="Game",
            category=another_category,
            price="80.00",
        )
        create_promo_code(
            code="MIXED", discount_percent="10.00", categories=[self.category]
        )

        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [
                    {"good_id": allowed_product.id, "quantity": 2},
                    {"good_id": excluded_product.id, "quantity": 1},
                    {"good_id": another_product.id, "quantity": 1},
                ],
                "promo_code": "MIXED",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["price"], "330.00")
        self.assertEqual(response.data["total"], "310.00")
        self.assertEqual(response.data["discount"], "0.0606")

        goods_by_id = {item["good_id"]: item for item in response.data["goods"]}
        self.assertEqual(goods_by_id[allowed_product.id]["discount"], "0.1000")
        self.assertEqual(goods_by_id[allowed_product.id]["total"], "180.00")
        self.assertEqual(goods_by_id[excluded_product.id]["discount"], "0.0000")
        self.assertEqual(goods_by_id[excluded_product.id]["total"], "50.00")
        self.assertEqual(goods_by_id[another_product.id]["discount"], "0.0000")
        self.assertEqual(goods_by_id[another_product.id]["total"], "80.00")

    def test_duplicate_goods_are_rejected_by_service(self):
        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [
                    {"good_id": self.product.id, "quantity": 1},
                    {"good_id": self.product.id, "quantity": 2},
                ],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"goods": ["Duplicate goods are not allowed."]})

    def test_promo_error_rolls_back_order_creation(self):
        create_promo_code(
            code="OLD_ROLLBACK",
            valid_until=timezone.now() - timezone.timedelta(days=1),
            categories=[self.category],
        )

        response = self.post_order(
            {
                "user_id": self.user.id,
                "goods": [{"good_id": self.product.id, "quantity": 1}],
                "promo_code": "OLD_ROLLBACK",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PromoCodeUsage.objects.count(), 0)


class PromoCodeServiceTests(TestCase):
    def test_discount_percent_is_converted_to_rate(self):
        promo_code = create_promo_code(discount_percent="12.50")

        self.assertEqual(
            PromoCodeService.get_discount_rate(promo_code),
            Decimal("0.1250"),
        )

    def test_promo_without_categories_applies_to_any_non_excluded_product(self):
        product = create_product()
        promo_code = create_promo_code()

        self.assertTrue(PromoCodeService.can_apply_to_product(promo_code, product))

    def test_inactive_promo_code_is_invalid(self):
        user = create_user("inactive-user")
        promo_code = create_promo_code(is_active=False)

        with self.assertRaisesMessage(
            PromoCodeValidationError,
            "Promo code is not active.",
        ):
            PromoCodeService.validate_for_user(promo_code, user.id)

    def test_get_locked_promo_code_uses_select_for_update(self):
        create_promo_code(code="LOCKED")

        with patch.object(
            PromoCode.objects,
            "select_for_update",
            wraps=PromoCode.objects.select_for_update,
        ) as select_for_update:
            PromoCodeService.get_locked_promo_code("LOCKED")

        select_for_update.assert_called_once_with()


class PromoCodeRaceConditionTests(TransactionTestCase):
    reset_sequences = True

    def test_only_one_order_can_use_last_available_promo_code(self):
        category = create_category("Race")
        product = create_product(category=category, price="100.00")
        promo_code = create_promo_code(code="LAST", max_uses=1, categories=[category])
        users = [create_user("race-1"), create_user("race-2")]
        start_barrier = Barrier(2)

        def create_order(user_id: int) -> str:
            connections.close_all()
            try:
                start_barrier.wait()
                OrderService.create_order(
                    user_id=user_id,
                    goods=[{"good_id": product.id, "quantity": 1}],
                    promo_code=promo_code.code,
                )
                return "created"
            except PromoCodeValidationError:
                return "rejected"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create_order, user.id) for user in users]
            results = [future.result() for future in as_completed(futures)]

        self.assertEqual(results.count("created"), 1)
        self.assertEqual(results.count("rejected"), 1)
        self.assertEqual(
            PromoCodeUsage.objects.filter(promo_code=promo_code).count(), 1
        )
        self.assertEqual(Order.objects.filter(promo_code=promo_code).count(), 1)
