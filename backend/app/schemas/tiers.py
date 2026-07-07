from typing import Optional, List, Any
from pydantic import BaseModel


class TierUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_amount: Optional[int] = None
    price_amount_yearly: Optional[int] = None
    highlights: Optional[List[str]] = None
    is_popular: Optional[bool] = None

class TierResponse(BaseModel):
    id: int
    level: int
    name: str
    description: Optional[str] = None
    price_amount: int
    price_amount_yearly: Optional[int] = None
    currency: str
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    stripe_yearly_price_id: Optional[str] = None
    highlights: Optional[Any] = None
    is_popular: bool
    icon: Optional[str] = None

    class Config:
        from_attributes = True
