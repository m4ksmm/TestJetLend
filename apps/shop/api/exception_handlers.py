from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.shop.exceptions import ShopError


def api_exception_handler(exc, context):
    if isinstance(exc, ShopError):
        return Response({exc.field: [exc.message]}, status=exc.status_code)

    return exception_handler(exc, context)
