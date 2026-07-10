from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api import deps
from app.models.users import User
from app.services.portfolio_service import STRESS_SCENARIOS, PortfolioService

router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio"])


class PortfolioAsset(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    weight: float = Field(
        ..., description="Weight of the asset in the portfolio (0.0 to 1.0)"
    )


class StressTestRequest(BaseModel):
    portfolio: list[PortfolioAsset] = Field(
        ..., min_length=1, description="List of assets in the portfolio"
    )
    scenarios: list[str] | None = Field(
        None, description="Optional list of stress scenario IDs to execute"
    )


class CrisisResult(BaseModel):
    return_pct: float
    max_drawdown: float
    status: str


class StressTestResponse(BaseModel):
    crises: dict[str, CrisisResult]


class ScenarioMetadata(BaseModel):
    id: str
    name: str
    category: str
    description: str
    type: str
    start_date: str | None = None
    end_date: str | None = None


@router.get("/stress-test/scenarios", response_model=list[ScenarioMetadata])
def get_stress_scenarios(
    _current_user: User = Depends(deps.get_current_user),
):
    """
    Get the metadata for all available historical and hypothetical stress testing scenarios.
    """
    metadata_list = []
    for sc_id, data in STRESS_SCENARIOS.items():
        metadata_list.append(
            ScenarioMetadata(
                id=sc_id,
                name=data["name"],
                category=data["category"],
                description=data["description"],
                type=data["type"],
                start_date=data.get("start"),
                end_date=data.get("end"),
            )
        )
    return metadata_list


@router.post("/stress-test", response_model=StressTestResponse)
def run_stress_test(
    request: StressTestRequest,
    _current_user: User = Depends(deps.get_current_user),
):
    """
    Run a portfolio stress test against historical crises or custom selected scenarios.
    """
    portfolio_dicts = [
        {"ticker": asset.ticker, "weight": asset.weight} for asset in request.portfolio
    ]

    results = PortfolioService.calculate_stress_test(portfolio_dicts, request.scenarios)
    if "error" in results:
        raise HTTPException(status_code=400, detail=results["error"])

    return StressTestResponse(crises=results)
