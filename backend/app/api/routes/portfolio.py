from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api import deps
from app.models.users import User
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio"])


class PortfolioAsset(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    weight: float = Field(
        ..., description="Weight of the asset in the portfolio (0.0 to 1.0)"
    )


class StressTestRequest(BaseModel):
    portfolio: list[PortfolioAsset] = Field(..., min_length=1, description="List of assets in the portfolio")


class CrisisResult(BaseModel):
    return_pct: float
    max_drawdown: float
    status: str


class StressTestResponse(BaseModel):
    crises: dict[str, CrisisResult]


@router.post("/stress-test", response_model=StressTestResponse)
def run_stress_test(
    request: StressTestRequest,
    _current_user: User = Depends(deps.get_current_user),
):
    """
    Run a portfolio stress test against historical crises (2008 Crash, 2020 COVID).
    """
    portfolio_dicts = [
        {"ticker": asset.ticker, "weight": asset.weight} for asset in request.portfolio
    ]

    results = PortfolioService.calculate_stress_test(portfolio_dicts)
    if "error" in results:
        raise HTTPException(status_code=400, detail=results["error"])

    return StressTestResponse(crises=results)
