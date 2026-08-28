import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api import deps
from app.core.config import settings
from app.models.users import User

router = APIRouter(prefix="/api/v1/research", tags=["Research"])

# Minimum tier required to access research reports - matches the ml service's own
# defense-in-depth check in src/api/routes/research.py.
_MIN_RESEARCH_TIER = 2

_ML_REQUEST_TIMEOUT_SECONDS = 60.0


class ResearchReportRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=100)


@router.post("/report")
async def get_research_report(
    request: ResearchReportRequest,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Proxy a research report request to the ML service, using the caller's real
    subscription tier (never a client-supplied one) for entitlement + quota.
    """
    tier_level = 1
    if current_user.subscription and current_user.subscription.tier:
        tier_level = current_user.subscription.tier.level

    if tier_level < _MIN_RESEARCH_TIER:
        raise HTTPException(
            status_code=403,
            detail=f"Research reports require tier {_MIN_RESEARCH_TIER} or higher.",
        )

    async with httpx.AsyncClient(timeout=_ML_REQUEST_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(
                f"{settings.ML_API_URL}/api/v1/research/report",
                json={"ticker": request.ticker, "tier": tier_level},
                headers={
                    "x-user-id": str(current_user.id),
                    "x-tier-id": str(tier_level),
                },
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail="Research service is unavailable."
            ) from exc

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=_extract_detail(response))

    return response.json()


def _extract_detail(response: httpx.Response) -> str:
    """Pull a plain error message out of the ml service's response.

    FastAPI error responses are JSON `{"detail": "..."}`; re-raising the raw
    body as-is would double-encode that JSON inside our own `detail` field.
    """
    try:
        body = response.json()
        if isinstance(body, dict) and isinstance(body.get("detail"), str):
            return body["detail"]
    except ValueError:
        pass
    return response.text or "Research service returned an unexpected error."
