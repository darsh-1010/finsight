from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class TokenUsage(BaseModel):
    user_id: int
    tier_level: int
    tier_name: str
    available_tokens: int
    total_used_tokens: int
    daily_tokens_used: int
    daily_token_limit: int
    weekly_tokens: int
    monthly_token_limit: int | None = None
    max_tokens_per_prompt: int
    refill_frequency: str
    last_refill_at: datetime | None = None
    next_refill_at: datetime | None = None
    usage_date: date

    model_config = ConfigDict(from_attributes=True)


class TokenTransactionOut(BaseModel):
    id: int
    transaction_type: str
    tokens: int
    balance_before: int
    balance_after: int
    reference_type: str | None = None
    reference_id: int | None = None
    description: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenTransactionList(BaseModel):
    items: list[TokenTransactionOut]
    limit: int
    offset: int
