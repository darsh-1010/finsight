"""Tier policy definitions and feature flags."""

from dataclasses import dataclass

from config.settings import settings


@dataclass(frozen=True)
class TierFeatures:
    """Feature entitlements for a specific tier."""

    name: str
    search_depth: int  # How many chunks to retrieve per search
    has_web_access: bool  # Access to research-article context
    max_tokens: int  # Hard cap on LLM response tokens
    prompt_profile: str  # Which system prompt profile to load
    has_reasoning_trace: bool  # Show "Reasoning" thoughts to user
    has_quant_access: bool  # Can use volatility/risk tools
    direct_llm_only: bool  # Skip query analysis and retrieval orchestration
    quota_daily_requests: int  # Daily limit (optional middleware enforcement)
    model_name: str  # The LLM model assigned to this tier
    document_search_depth: int | None = None  # Specific limit for RAG documents
    article_search_depth: int | None = None  # Specific limit for web articles


# Default tier to use when resolution fails
DEFAULT_TIER_ID = 1

# Static fallback policy (Truth Source: Backend Database)
# These are kept as safe defaults if cache/DB is unreachable.
TIER_POLICIES: dict[int, TierFeatures] = {
    0: TierFeatures(
        name="Tier 0 (Guest)",
        search_depth=0,
        has_web_access=False,
        max_tokens=768,
        prompt_profile="guest",
        has_reasoning_trace=False,
        has_quant_access=False,
        direct_llm_only=True,
        quota_daily_requests=settings.tier_0_quota,
        model_name=settings.tier_0_model,
    ),
    1: TierFeatures(
        name="Tier 1 (Starter)",
        search_depth=0,
        has_web_access=False,
        max_tokens=512,
        prompt_profile="concise",
        has_reasoning_trace=False,
        has_quant_access=False,
        direct_llm_only=False,
        quota_daily_requests=settings.tier_1_quota,
        model_name=settings.tier_1_model,
    ),
    2: TierFeatures(
        name="Tier 2 (Growth)",
        search_depth=3,
        has_web_access=True,
        max_tokens=1024,
        prompt_profile="standard",
        has_reasoning_trace=False,
        has_quant_access=False,
        direct_llm_only=False,
        quota_daily_requests=settings.tier_2_quota,
        model_name=settings.tier_2_model,
        document_search_depth=2,
        article_search_depth=2,
    ),
    3: TierFeatures(
        name="Tier 3 (Premium)",
        search_depth=10,
        has_web_access=True,
        max_tokens=2048,
        prompt_profile="synthesis",
        has_reasoning_trace=True,
        has_quant_access=False,
        direct_llm_only=False,
        quota_daily_requests=settings.tier_3_quota,
        model_name=settings.tier_3_model,
    ),
    4: TierFeatures(
        name="Tier 4 (Enterprise)",
        search_depth=25,
        has_web_access=True,
        max_tokens=4096,
        prompt_profile="pro",
        has_reasoning_trace=True,
        has_quant_access=True,
        direct_llm_only=False,
        quota_daily_requests=settings.tier_4_quota,
        model_name=settings.tier_4_model,
    ),
}


def get_static_policy(tier_id: int) -> TierFeatures:
    """Get the hardcoded fallback policy for a tier ID."""
    return TIER_POLICIES.get(tier_id, TIER_POLICIES[DEFAULT_TIER_ID])
