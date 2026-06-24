from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shop.api.serializers import OrderCreateSerializer, OrderResponseSerializer
from apps.shop.services.order_service import OrderService


class OrderCreateAPIView(APIView):
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = OrderService.create_order(**serializer.validated_data)
        response_serializer = OrderResponseSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
