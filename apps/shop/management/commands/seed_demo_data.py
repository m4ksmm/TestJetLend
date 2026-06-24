from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.shop.models import Category, Product, PromoCode


class Command(BaseCommand):
    help = "Seed demo data for local development."

    def handle(self, *args, **options):
        with transaction.atomic():
            users = self._create_users()
            categories = self._create_categories()
            products = self._create_products(categories)
            promo_codes = self._create_promo_codes(categories)

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self._print_summary(users, products, promo_codes)

    def _create_users(self) -> dict[str, AbstractBaseUser]:
        user_model = get_user_model()
        users = {}
        for username in ("demo", "second_user"):
            user, _ = user_model.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com"},
            )
            user.set_password("password")
            user.save(update_fields=["password"])
            users[username] = user
        return users

    def _create_categories(self) -> dict[str, Category]:
        categories = {}
        for name in ("Books", "Electronics", "Gift Cards"):
            category, _ = Category.objects.get_or_create(name=name)
            categories[name] = category
        return categories

    def _create_products(self, categories: dict[str, Category]) -> dict[str, Product]:
        product_specs = {
            "Clean Architecture": {
                "category": categories["Books"],
                "price": Decimal("100.00"),
                "is_promo_excluded": False,
            },
            "Wireless Keyboard": {
                "category": categories["Electronics"],
                "price": Decimal("250.00"),
                "is_promo_excluded": False,
            },
            "Gift Card 100": {
                "category": categories["Gift Cards"],
                "price": Decimal("100.00"),
                "is_promo_excluded": True,
            },
        }

        products = {}
        for name, values in product_specs.items():
            product, _ = Product.objects.update_or_create(
                name=name,
                defaults=values,
            )
            products[name] = product
        return products

    def _create_promo_codes(
        self, categories: dict[str, Category]
    ) -> dict[str, PromoCode]:
        now = timezone.now()
        promo_specs = {
            "SUMMER2025": {
                "discount_percent": Decimal("10.00"),
                "valid_until": now + timezone.timedelta(days=30),
                "max_uses": 100,
                "is_active": True,
                "categories": [],
            },
            "BOOKS10": {
                "discount_percent": Decimal("10.00"),
                "valid_until": now + timezone.timedelta(days=30),
                "max_uses": 50,
                "is_active": True,
                "categories": [categories["Books"]],
            },
            "LIMIT1": {
                "discount_percent": Decimal("20.00"),
                "valid_until": now + timezone.timedelta(days=30),
                "max_uses": 1,
                "is_active": True,
                "categories": [],
            },
            "EXPIRED": {
                "discount_percent": Decimal("15.00"),
                "valid_until": now - timezone.timedelta(days=1),
                "max_uses": 100,
                "is_active": True,
                "categories": [],
            },
            "INACTIVE": {
                "discount_percent": Decimal("15.00"),
                "valid_until": now + timezone.timedelta(days=30),
                "max_uses": 100,
                "is_active": False,
                "categories": [],
            },
        }

        promo_codes = {}
        for code, values in promo_specs.items():
            categories_for_code = values.pop("categories")
            promo_code, _ = PromoCode.objects.update_or_create(
                code=code,
                defaults=values,
            )
            promo_code.categories.set(categories_for_code)
            promo_codes[code] = promo_code
        return promo_codes

    def _print_summary(
        self,
        users: dict[str, AbstractBaseUser],
        products: dict[str, Product],
        promo_codes: dict[str, PromoCode],
    ) -> None:
        self.stdout.write("")
        self.stdout.write("Users:")
        for username, user in users.items():
            self.stdout.write(f"  {username}: id={user.id}, password=password")

        self.stdout.write("")
        self.stdout.write("Products:")
        for name, product in products.items():
            excluded = " excluded from promos" if product.is_promo_excluded else ""
            self.stdout.write(
                f"  {name}: id={product.id}, price={product.price}{excluded}"
            )

        self.stdout.write("")
        self.stdout.write("Promo codes:")
        for code, promo_code in promo_codes.items():
            self.stdout.write(
                f"  {code}: discount={promo_code.discount_percent}%, "
                f"max_uses={promo_code.max_uses}, active={promo_code.is_active}"
            )

        demo_user = users["demo"]
        demo_product = products["Clean Architecture"]
        self.stdout.write("")
        self.stdout.write("Example request:")
        self.stdout.write(
            "  curl -X POST http://127.0.0.1:8000/api/orders/ "
            '-H "Content-Type: application/json" '
            f'-d \'{{"user_id": {demo_user.id}, '
            f'"goods": [{{"good_id": {demo_product.id}, "quantity": 2}}], '
            '"promo_code": "SUMMER2025"}\''
        )
