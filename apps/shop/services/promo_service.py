from decimal import Decimal

from django.utils import timezone

from apps.shop.exceptions import PromoCodeValidationError
from apps.shop.models import Product, PromoCode, PromoCodeUsage


class PromoCodeService:
    DISCOUNT_DIVISOR = Decimal("100")

    @classmethod
    def get_locked_promo_code(cls, code: str) -> PromoCode:
        try:
            return (
                PromoCode.objects.select_for_update()
                .prefetch_related("categories")
                .get(code=code)
            )
        except PromoCode.DoesNotExist as exc:
            raise PromoCodeValidationError("Promo code does not exist.") from exc

    @classmethod
    def validate_for_user(cls, promo_code: PromoCode, user_id: int) -> None:
        if not promo_code.is_active:
            raise PromoCodeValidationError("Promo code is not active.")

        if promo_code.valid_until < timezone.now():
            raise PromoCodeValidationError("Promo code has expired.")

        usages_count = promo_code.usages.count()
        if usages_count >= promo_code.max_uses:
            raise PromoCodeValidationError("Promo code usage limit has been reached.")

        if PromoCodeUsage.objects.filter(
            user_id=user_id, promo_code=promo_code
        ).exists():
            raise PromoCodeValidationError("User has already used this promo code.")

    @classmethod
    def get_discount_rate(cls, promo_code: PromoCode) -> Decimal:
        return (promo_code.discount_percent / cls.DISCOUNT_DIVISOR).quantize(
            Decimal("0.0001")
        )

    @classmethod
    def can_apply_to_product(cls, promo_code: PromoCode, product: Product) -> bool:
        if product.is_promo_excluded:
            return False

        category_ids = {category.id for category in promo_code.categories.all()}
        if not category_ids:
            return True

        return product.category_id in category_ids
