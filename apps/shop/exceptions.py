class ShopError(Exception):
    default_field = "error"
    status_code = 400

    def __init__(self, message: str, field: str | None = None) -> None:
        self.message = message
        self.field = field or self.default_field
        super().__init__(message)


class OrderValidationError(ShopError):
    pass


class PromoCodeValidationError(OrderValidationError):
    default_field = "promo_code"
