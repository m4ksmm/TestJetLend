from django.urls import path

from apps.shop.api.views import OrderCreateAPIView

app_name = "shop"

urlpatterns = [
    path("orders/", OrderCreateAPIView.as_view(), name="order-create"),
]
