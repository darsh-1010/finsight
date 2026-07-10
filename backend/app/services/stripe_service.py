import stripe

from app.core.config import settings

# Configure stripe API key if available
stripe.api_key = getattr(settings, "STRIPE_API_KEY", "mock_stripe_key")


class StripeService:
    @staticmethod
    def get_or_create_customer(db, user):
        """Mock creation of stripe customer."""
        return "cus_mock_12345"

    @staticmethod
    def archive_price(price_id: str):
        """Mock archive stripe price."""
        if not price_id or "mock" in price_id:
            return
        try:
            stripe.Price.modify(price_id, active=False)
        except Exception:
            pass

    @staticmethod
    def create_price(product_id: str, amount: int, interval: str):
        """Mock create stripe price."""
        if not product_id or "mock" in product_id:
            return f"price_mock_{interval}_{amount}"
        try:
            price = stripe.Price.create(
                unit_amount=amount,
                currency="usd",
                recurring={"interval": interval},
                product=product_id,
            )
            return price.id
        except Exception:
            return f"price_mock_{interval}_{amount}"
