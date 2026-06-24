from django.contrib import admin

from apps.shop.models import (
    Category,
    Order,
    OrderItem,
    Product,
    PromoCode,
    PromoCodeUsage,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "category", "price", "is_promo_excluded"]
    list_filter = ["category", "is_promo_excluded"]
    search_fields = ["name"]
    autocomplete_fields = ["category"]


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "code",
        "discount_percent",
        "valid_until",
        "max_uses",
        "is_active",
    ]
    list_filter = ["is_active", "categories"]
    search_fields = ["code"]
    filter_horizontal = ["categories"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "quantity", "price", "discount", "total"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "promo_code",
        "price",
        "discount",
        "total",
        "created_at",
    ]
    list_filter = ["created_at", "promo_code"]
    date_hierarchy = "created_at"
    search_fields = ["user__username", "promo_code__code"]
    readonly_fields = ["user", "promo_code", "price", "discount", "total", "created_at"]
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "product", "quantity", "price", "discount", "total"]
    list_filter = ["product__category"]
    readonly_fields = ["order", "product", "quantity", "price", "discount", "total"]


@admin.register(PromoCodeUsage)
class PromoCodeUsageAdmin(admin.ModelAdmin):
    list_display = ["user", "promo_code", "order", "created_at"]
    search_fields = ["user__username", "promo_code__code"]
    readonly_fields = ["user", "promo_code", "order", "created_at"]
