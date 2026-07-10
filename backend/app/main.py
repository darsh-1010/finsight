from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import (
    admin,
    auth,
    chat,
    content,
    market,
    ml_data_transfer,
    notifications,
    onboarding,
    payments,
    portfolio,
    scraping,
    tiers,
    tokens,
    websockets,
)
from .core.config import settings
from .core.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tiers.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(content.router)
app.include_router(onboarding.router)
app.include_router(chat.router)
app.include_router(websockets.router)
app.include_router(scraping.router)
app.include_router(ml_data_transfer.router)
app.include_router(market.router)
app.include_router(tokens.router)
app.include_router(notifications.router)
app.include_router(portfolio.router)

from .services.cron import cron_service


@app.on_event("startup")
async def _startup_event() -> None:
    try:
        await cron_service.start()
    except Exception:
        import logging

        logging.getLogger("cron").exception("Failed to start cron service")


@app.on_event("shutdown")
async def _shutdown_event() -> None:
    try:
        await cron_service.stop()
    except Exception:
        import logging

        logging.getLogger("cron").exception("Failed to stop cron service")


@app.get("/")
def read_root():
    return {"message": "Welcome to FastAPI Backend"}
