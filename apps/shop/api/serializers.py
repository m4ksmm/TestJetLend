from rest_framework import serializers


class GoodInputSerializer(serializers.Serializer):
    good_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    goods = GoodInputSerializer(many=True, allow_empty=False)
    promo_code = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=64,
    )


class OrderItemResponseSerializer(serializers.Serializer):
    good_id = serializers.IntegerField(source="product_id")
    quantity = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount = serializers.DecimalField(max_digits=5, decimal_places=4)
    total = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderResponseSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    order_id = serializers.IntegerField(source="id")
    goods = OrderItemResponseSerializer(source="items", many=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount = serializers.DecimalField(max_digits=5, decimal_places=4)
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
