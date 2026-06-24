from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "category"
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=160)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_promo_excluded = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "product"
        verbose_name_plural = "products"
        indexes = [
            models.Index(fields=["category", "is_promo_excluded"]),
        ]
        constraints = [
            models.CheckConstraint(check=Q(price__gte=0), name="product_price_gte_0"),
        ]

    def __str__(self) -> str:
        return self.name


class PromoCode(models.Model):
    code = models.CharField(max_length=64, unique=True)
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Stored as percent: 10.00 means 10%.",
    )
    valid_until = models.DateTimeField()
    max_uses = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name="promo_codes",
        help_text="Empty list means the promo code applies to all categories.",
    )

    class Meta:
        ordering = ["code"]
        verbose_name = "promo code"
        verbose_name_plural = "promo codes"
        indexes = [
            models.Index(fields=["is_active", "valid_until"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(discount_percent__gte=0) & Q(discount_percent__lte=100),
                name="promo_discount_percent_between_0_and_100",
            ),
            models.CheckConstraint(check=Q(max_uses__gt=0), name="promo_max_uses_gt_0"),
        ]

    def __str__(self) -> str:
        return self.code


class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "order"
        verbose_name_plural = "orders"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["promo_code", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(check=Q(price__gte=0), name="order_price_gte_0"),
            models.CheckConstraint(
                check=Q(discount__gte=0) & Q(discount__lte=1),
                name="order_discount_between_0_and_1",
            ),
            models.CheckConstraint(check=Q(total__gte=0), name="order_total_gte_0"),
        ]

    def __str__(self) -> str:
        return f"Order #{self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]
        verbose_name = "order item"
        verbose_name_plural = "order items"
        indexes = [
            models.Index(fields=["order", "product"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(quantity__gt=0), name="order_item_quantity_gt_0"
            ),
            models.CheckConstraint(
                check=Q(price__gte=0), name="order_item_price_gte_0"
            ),
            models.CheckConstraint(
                check=Q(discount__gte=0) & Q(discount__lte=1),
                name="order_item_discount_between_0_and_1",
            ),
            models.CheckConstraint(
                check=Q(total__gte=0), name="order_item_total_gte_0"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} x {self.quantity}"


class PromoCodeUsage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="promo_code_usages",
    )
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.CASCADE,
        related_name="usages",
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="promo_usage",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "promo code usage"
        verbose_name_plural = "promo code usages"
        indexes = [
            models.Index(fields=["promo_code", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "promo_code"],
                name="unique_user_promo_code_usage",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.promo_code.code}"
