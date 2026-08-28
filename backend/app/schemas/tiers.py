from typing import Any

from pydantic import BaseModel


class TierUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price_amount: int | None = None
    price_amount_yearly: int | None = None
    highlights: list[str] | None = None
    is_popular: bool | None = None


class TierResponse(BaseModel):
    id: int
    level: int
    name: str
    description: str | None = None
    price_amount: int
    price_amount_yearly: int | None = None
    currency: str
    highlights: Any | None = None
    is_popular: bool
    icon: str | None = None

    class Config:
        from_attributes = True
