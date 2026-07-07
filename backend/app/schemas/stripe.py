from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class StripeCustomerBase(BaseModel):
    stripe_customer_id: str

class StripeCustomerCreate(StripeCustomerBase):
    pass

class StripeCustomer(StripeCustomerBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SubscriptionBase(BaseModel):
    stripe_subscription_id: Optional[str] = None
    status: str
    current_period_end: Optional[datetime] = None

class CheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str

class PortalSessionRequest(BaseModel):
    return_url: str

class BillingDetailsResponse(BaseModel):
    status: str
    next_billing_date: Optional[datetime] = None
    card_last4: Optional[str] = None
    card_brand: Optional[str] = None
    cancel_at_period_end: Optional[bool] = False
    scheduled_tier_level: Optional[int] = None

class UpdateSubscriptionRequest(BaseModel):
    price_id: str

class PreviewSubscriptionResponse(BaseModel):
    is_downgrade: bool
    amount_due_today: float
    next_billing_date: int
    new_total: float
    currency: str
    unused_credit_balance: Optional[float] = 0.0
    credit_applied_today: Optional[float] = 0.0
    is_yearly_to_monthly: Optional[bool] = False

class InvoiceItem(BaseModel):
    id: str
    created: int
    amount_paid: float
    currency: str
    status: str
    invoice_pdf: Optional[str] = None
    description: str
