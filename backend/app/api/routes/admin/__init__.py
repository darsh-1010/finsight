from fastapi import APIRouter

from . import brokers, compliance, insights, onboarding, scraping, signals, tiers

router = APIRouter(prefix="/api/v1/admin")

router.include_router(compliance.router)
router.include_router(signals.router)
router.include_router(insights.router)
router.include_router(brokers.router)
router.include_router(tiers.router)
router.include_router(onboarding.router)
router.include_router(scraping.router)
