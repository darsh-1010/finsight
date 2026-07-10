"""
CronService
===========
Manages all scheduled background jobs for the backend.

Registered jobs
---------------
- **Token wallet refill**   – runs on every tick (interval-based, default 600 s)
- **Daily insights sync**   – runs once per day at 06:00 IST
- **Weekly insights sync**  – runs once per week on Saturday at 06:00 IST

IST = UTC+5:30, so 06:00 IST == 00:30 UTC.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SESSION_LOCAL
from app.models.insights import Insight, InsightStatus
from app.models.subscriptions import Subscription, SubscriptionStatus
from app.models.tiers import Tier
from app.models.tokens import TierTokenConfig, UserTokenWallets
from app.models.users import User
from app.services.insights_sync_service import sync_insights
from app.services.portfolio_service import PortfolioService
from app.services.ses_service import SESService
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

# IST offset
_IST = timezone(timedelta(hours=5, minutes=30))

# Target time for both cron jobs
_TARGET_HOUR_IST = settings.CRON_INSIGHTS_SYNC_HOUR_IST
_TARGET_MINUTE_IST = settings.CRON_INSIGHTS_SYNC_MINUTE_IST


# Day-of-week for weekly job (Monday=0 … Sunday=6)
_WEEKLY_SYNC_DAY = settings.CRON_WEEKLY_INSIGHTS_SYNC_DAY


# ---------------------------------------------------------------------------
# Existing job: token wallet refill
# ---------------------------------------------------------------------------


def refill_due_token_wallets(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()

    due_wallets = (
        db.query(User, Tier, TierTokenConfig)
        .join(UserTokenWallets, UserTokenWallets.user_id == User.id)
        .join(Subscription, Subscription.user_id == User.id)
        .join(Tier, Tier.id == Subscription.tier_id)
        .join(TierTokenConfig, TierTokenConfig.tier_id == Tier.id)
        .filter(
            UserTokenWallets.next_refill_at.isnot(None),
            UserTokenWallets.next_refill_at <= now,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .all()
    )

    for user, tier, token_config in due_wallets:
        TokenService.refill_wallet_for_tier(
            db,
            user,
            tier,
            transaction_type="refill",
            description=f"Scheduled token refill for {tier.name}",
            extra_metadata={
                "source": "cron",
                "tier_token_config_id": token_config.id,
                "refill_frequency": token_config.refill_frequency,
            },
            now=now,
        )

    return len(due_wallets)


async def run_cron_jobs(db: Session) -> None:
    """Interval-based tick: run the token wallet refill job."""
    refilled_count = refill_due_token_wallets(db)
    logger.info("Cron tick completed. Refilled %s token wallet(s).", refilled_count)


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------


def _seconds_until_next_ist(hour: int, minute: int) -> float:
    """Return how many seconds remain until the next occurrence of *hour*:*minute* IST."""
    now_ist = datetime.now(tz=_IST)
    target_today = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now_ist >= target_today:
        # Already past today's window → aim for tomorrow
        target_today += timedelta(days=1)
    return (target_today - now_ist).total_seconds()


def _seconds_until_next_weekly_ist(hour: int, minute: int) -> float:
    """Return seconds until the next weekly run day at *hour*:*minute* IST."""
    now_ist = datetime.now(tz=_IST)
    days_ahead = (_WEEKLY_SYNC_DAY - now_ist.weekday()) % 7
    target = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
    target += timedelta(days=days_ahead)
    if now_ist >= target:
        # It's the target day but the window has passed → next week
        target += timedelta(weeks=1)
    return (target - now_ist).total_seconds()


# ---------------------------------------------------------------------------
# Individual scheduled job coroutines
# ---------------------------------------------------------------------------


def archive_expired_insights(db: Session) -> int:
    """Find all insights that are past their expiration date and not archived yet, and update status to archived."""
    now = datetime.utcnow()
    expired = (
        db.query(Insight)
        .filter(
            Insight.expires_at.isnot(None),
            Insight.expires_at <= now,
            Insight.status != InsightStatus.ARCHIVED,
        )
        .all()
    )
    for insight in expired:
        insight.status = InsightStatus.ARCHIVED
    if expired:
        logger.info("Archived %d expired insight(s).", len(expired))
    return len(expired)


async def _run_daily_insights_job(stop_event: asyncio.Event) -> None:
    """Loop that fires the daily insights sync every day at 06:00 IST."""
    while not stop_event.is_set():
        wait_secs = _seconds_until_next_ist(_TARGET_HOUR_IST, _TARGET_MINUTE_IST)
        logger.info(
            "Daily insights sync scheduled in %.0f s (next %02d:%02d IST).",
            wait_secs,
            _TARGET_HOUR_IST,
            _TARGET_MINUTE_IST,
        )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=wait_secs)
        except TimeoutError:
            pass

        if stop_event.is_set():
            break

        db: Session = SESSION_LOCAL()
        try:
            archive_expired_insights(db)
            count = await sync_insights(db, mode="daily")
            db.commit()
            logger.info("Daily insights sync complete — %d insight(s) saved.", count)
        except Exception:
            db.rollback()
            logger.exception("Daily insights sync failed")
        finally:
            db.close()


async def _run_weekly_insights_job(stop_event: asyncio.Event) -> None:
    """Loop that fires the weekly insights sync every Saturday at 06:00 IST."""
    while not stop_event.is_set():
        wait_secs = _seconds_until_next_weekly_ist(_TARGET_HOUR_IST, _TARGET_MINUTE_IST)
        logger.info(
            "Weekly insights sync scheduled in %.0f s (next weekly day %02d:%02d IST).",
            wait_secs,
            _TARGET_HOUR_IST,
            _TARGET_MINUTE_IST,
        )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=wait_secs)
        except TimeoutError:
            pass

        if stop_event.is_set():
            break

        db: Session = SESSION_LOCAL()
        try:
            archive_expired_insights(db)
            count = await sync_insights(db, mode="weekly")
            db.commit()
            logger.info("Weekly insights sync complete — %d insight(s) saved.", count)
        except Exception:
            db.rollback()
            logger.exception("Weekly insights sync failed")
        finally:
            db.close()


async def _run_weekly_email_briefing_job(stop_event: asyncio.Event) -> None:
    """Loop that sends weekly email briefings using yfinance metrics."""
    while not stop_event.is_set():
        wait_secs = _seconds_until_next_weekly_ist(_TARGET_HOUR_IST, _TARGET_MINUTE_IST)
        logger.info(
            "Weekly email briefing scheduled in %.0f s (next weekly day %02d:%02d IST).",
            wait_secs,
            _TARGET_HOUR_IST,
            _TARGET_MINUTE_IST,
        )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=wait_secs)
        except TimeoutError:
            pass

        if stop_event.is_set():
            break

        db: Session = SESSION_LOCAL()
        try:
            # Default watchlist for briefing
            default_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
            perf_data = PortfolioService.get_7_day_performance(default_tickers)

            if perf_data:
                # Load Jinja template
                template_dir = Path(__file__).parent.parent / "templates" / "email"
                env = Environment(loader=FileSystemLoader(str(template_dir)))
                template = env.get_template("weekly_briefing.html")

                # Fetch all active users who have an email
                users = (
                    db.query(User).filter(User.is_active, User.email.isnot(None)).all()
                )
                ses_service = SESService()

                for user in users:
                    html_content = template.render(
                        name=user.full_name or user.email.split("@")[0],
                        perf=perf_data,
                        current_year=datetime.utcnow().year,
                    )

                    try:
                        ses_service.send_email(
                            to_email=str(user.email),
                            subject="Your Weekly Finsight Briefing",
                            html_content=html_content,
                        )
                        logger.info("Sent weekly briefing to %s", user.email)
                    except Exception as e:
                        logger.error(
                            "Failed to send weekly briefing to %s: %s", user.email, e
                        )

            logger.info("Weekly email briefing complete.")
        except Exception:
            logger.exception("Weekly email briefing failed")
        finally:
            db.close()


# ---------------------------------------------------------------------------
# CronService
# ---------------------------------------------------------------------------


class CronService:
    def __init__(self, interval_seconds: int = settings.CRON_INTERVAL_SECONDS) -> None:
        self.interval_seconds = interval_seconds

    async def run_once(self) -> None:
        """Run the interval-based jobs (token refill) a single time."""
        db = SESSION_LOCAL()
        try:
            await run_cron_jobs(db)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Cron job run failed")
        finally:
            db.close()

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        logger.info(
            "Cron service started (tick interval: %s s). "
            "Daily insights: %02d:%02d IST. Weekly insights: day %s at %02d:%02d IST.",
            self.interval_seconds,
            _TARGET_HOUR_IST,
            _TARGET_MINUTE_IST,
            _WEEKLY_SYNC_DAY,
            _TARGET_HOUR_IST,
            _TARGET_MINUTE_IST,
        )

        if settings.CRON_RUN_ON_START:
            await self.run_once()

        # Run all loops concurrently
        await asyncio.gather(
            self._run_interval_loop(stop_event),
            _run_daily_insights_job(stop_event),
            _run_weekly_insights_job(stop_event),
            _run_weekly_email_briefing_job(stop_event),
        )

        logger.info("Cron service stopped")

    async def _run_interval_loop(self, stop_event: asyncio.Event) -> None:
        """Existing tick-based loop (token wallet refill, etc.)."""
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                await self.run_once()
