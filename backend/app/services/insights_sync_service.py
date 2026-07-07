"""
InsightsSyncService
===================
Fetches market insights from the ML API for each tier (1–4) and persists
them to the `insights` table.  After a successful sync it creates a
`Notification` record targeted at all admin users.

Supported sync modes
--------------------
- daily  → GET /api/v1/alerts/daily?sync=true
- weekly → GET /api/v1/alerts/weekly?sync=true

Both endpoints require the following headers:
    x-user-id : 1             (fixed system user)
    x-tier-id : <tier id>     (called once per tier, tiers 1-4)

Expected ML-API response schema (list of alert objects):
    [
      {
        "ticker":              "AAPL",
        "summary":             "...",
        "source":              "Reuters",
        "trend":               "bullish",
        "trend_type":          "daily" | "weekly",
        "price_change_pct":    2.34,
        "key_event":           "Earnings beat",
        "verification_status": "verified",
        "citations":           ["https://..."],
        "alert_message":       "...",
      },
      ...
    ]

Any unknown / extra fields in the response are silently ignored.
"""

import logging
from typing import Literal

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.insights import Insight, InsightStatus, TrendType
from app.models.notifications import (
    AudienceType,
    Notification,
    NotificationAudience,
    NotificationPriority,
)

logger = logging.getLogger(__name__)

SyncMode = Literal["daily", "weekly"]

# ML API paths (sync=true triggers the ML side to refresh its cache)
_ML_PATHS: dict[SyncMode, str] = {
    "daily": "/api/v1/alerts/daily?sync=true",
    "weekly": "/api/v1/alerts/weekly?sync=true",
}

# Tiers to sync (tier 5 / Elite is excluded per requirement)
_SYNC_TIER_IDS = [1, 2, 3, 4]

# Fixed system user id sent as x-user-id
_SYSTEM_USER_ID = 1

# Per-tier request timeout in seconds.
# sync=true triggers ML computation which can take a long time.
_PER_TIER_TIMEOUT_SECS = 300


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_trend_type(value: str | None) -> TrendType | None:
    if not value:
        return None
    try:
        return TrendType(value.lower())
    except ValueError:
        return None


def _build_insight(payload: dict, mode: SyncMode, tier_id: int) -> Insight:
    """Map a single ML-API alert dict to an `Insight` ORM object."""
    trend_type = _coerce_trend_type(payload.get("trend_type") or mode)
    trend_key = "weekly_trend" if trend_type == TrendType.WEEKLY else "daily_trend"

    return Insight(
        ticker=payload.get("ticker"),
        summary=payload.get("summary"),
        source=payload.get("source"),
        trend=payload.get(trend_key) or payload.get("trend"),
        trend_type=trend_type,
        price_change_pct=payload.get("price_change_pct"),
        key_event=payload.get("key_event"),
        verification_status=payload.get("verification_status"),
        citations=payload.get("citations") or [],
        alert_message=payload.get("alert_message"),
        tier_required=tier_id,
        status=InsightStatus.DRAFT,
        published_at=None,
        expires_at=None,
    )


async def _fetch_for_tier(
    url: str,
    tier_id: int,
) -> list[dict]:
    """
    Call the ML API for a single tier with its own httpx client.
    Returns a list of alert dicts; never raises — errors are logged and
    an empty list is returned so remaining tiers continue.
    """
    headers = {
        "accept": "application/json",
        "x-user-id": str(_SYSTEM_USER_ID),
        "x-tier-id": str(tier_id),
    }
    logger.info("  → Fetching tier %d from %s", tier_id, url)
    try:
        # Each tier gets its own generous timeout because sync=true
        # triggers heavy ML computation on the server side.
        async with httpx.AsyncClient(timeout=_PER_TIER_TIMEOUT_SECS) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        logger.warning(
            "  ✗ Tier %d timed out after %ds — skipping.",
            tier_id,
            _PER_TIER_TIMEOUT_SECS,
        )
        return []
    except httpx.HTTPError as exc:
        logger.warning("  ✗ Tier %d HTTP error: %s — skipping.", tier_id, exc)
        return []

    if not response.is_success:
        logger.warning(
            "  ✗ Tier %d returned HTTP %s: %s",
            tier_id,
            response.status_code,
            response.text[:200],
        )
        return []

    data = response.json()

    if isinstance(data, dict):
        data = data.get("report", {}).get("highlights", [])

    count = len(data) if isinstance(data, list) else 0
    logger.info("  ✓ Tier %d: %d alert(s) received.", tier_id, count)
    return data if isinstance(data, list) else []


def _create_admin_notification(
    db: Session,
    mode: SyncMode,
    count: int,
    tiers_synced: list[int],
) -> Notification:
    """Insert a Notification + NotificationAudience row targeting all admins."""
    label = "Daily" if mode == "daily" else "Weekly"
    tier_str = ", ".join(f"Tier {t}" for t in tiers_synced)
    notification = Notification(
        title=f"New {label} Market Insights Available",
        message=(
            f"{count} new {mode} market insight(s) have been synced from the ML API "
            f"across {tier_str}. Visit the admin panel to review and publish them."
        ),
        notification_type="insight_sync",
        entity_type="insight",
        entity_id=None,
        priority=NotificationPriority.HIGH,
        action_url="/admin/insights",
        created_by="system",
        expires_at=None,
    )
    db.add(notification)
    db.flush()  # populate notification.id

    db.add(
        NotificationAudience(
            notification_id=notification.id,
            audience_type=AudienceType.ADMIN,
            audience_id=None,
        )
    )
    logger.info(
        "Admin notification created (id=%s) — %s sync, %d record(s).",
        notification.id,
        mode,
        count,
    )
    return notification


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


async def sync_insights(db: Session, mode: SyncMode) -> int:
    """
    Fetch insights from the ML API for *mode* across all eligible tiers
    (1–4) and persist them.

    Returns the total number of new `Insight` rows saved.
    Raises on unexpected errors so the caller can rollback.
    """
    base_url = settings.ML_API_URL.rstrip("/")
    url = f"{base_url}{_ML_PATHS[mode]}"

    tiers_to_sync = [3, 4] if mode == "daily" else [1, 2, 3, 4]

    logger.info(
        "Starting %s insights sync for tiers %s → %s",
        mode.upper(),
        tiers_to_sync,
        url,
    )

    all_insights: list[Insight] = []
    tiers_with_data: list[int] = []

    for tier_id in tiers_to_sync:
        alerts = await _fetch_for_tier(url, tier_id)

        if alerts:
            insights = [_build_insight(a, mode, tier_id) for a in alerts]
            all_insights.extend(insights)
            tiers_with_data.append(tier_id)

    total = len(all_insights)

    if total == 0:
        logger.info("No alerts returned across any tier for %s sync.", mode)
        return 0

    db.bulk_save_objects(all_insights)
    db.flush()

    notification = _create_admin_notification(db, mode, total, tiers_with_data)

    try:
        import json

        from app.api.routes.websockets import manager

        payload = json.dumps(
            {
                "type": "NEW_NOTIFICATION",
                "data": {
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                },
            }
        )
        await manager.broadcast(payload)
    except Exception as e:
        logger.warning("Failed to broadcast WS notification for synced insights: %s", e)

    logger.info(
        "%s sync complete — %d insight(s) saved across tier(s) %s.",
        mode.upper(),
        total,
        tiers_with_data,
    )
    return total
