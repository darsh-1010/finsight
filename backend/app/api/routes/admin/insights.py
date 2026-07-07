from datetime import datetime, timedelta
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_role
from app.models.users import User
from app.models.insights import Insight, InsightStatus, MarketInsightReview
from app.models.notifications import Notification, NotificationAudience, AudienceType, NotificationPriority
from app.schemas.admin import ApprovalRequest, InsightStatusUpdateRequest
from app.schemas.content import InsightResponse
import json
from app.api.routes.websockets import manager


router = APIRouter(prefix="/insights", tags=["Admin Insights"])


def _parse_insight_uuid(entity_id: int | str) -> uuid.UUID:
    try:
        return uuid.UUID(str(entity_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid insight UUID format") from exc


def _apply_status_update(
    item: Insight,
    request: InsightStatusUpdateRequest,
    current_user: User,
    db: Session,
) -> Optional[Notification]:
    item.status = request.status
    created_notification = None

    if request.status == InsightStatus.APPROVED:
        published_at = datetime.utcnow()
        item.published_at = published_at
        item.expires_at = published_at + timedelta(days=14)

        tab = item.trend_type.value if item.trend_type else "daily"
        action_url = f"/market_insights?tab={tab}&insightId={item.id}"
        
        notification_title = item.alert_message if item.alert_message else f"New Market Insight Available"
        notification = Notification(
            title=notification_title,
            message=item.summary or "A new market insight has been published.",
            notification_type="insight_update",
            entity_type="insight",
            entity_id=str(item.id),
            priority=NotificationPriority.MEDIUM,
            created_by=str(current_user.id),
            action_url=action_url,
        )
        audience = NotificationAudience(
            notification=notification,
            audience_type=AudienceType.TIER,
            audience_id=str(item.tier_required)
        )
        # audience_admin = NotificationAudience(
        #     notification=notification,
        #     audience_type=AudienceType.ADMIN,
        # )
        db.add(notification)
        db.add(audience)
        # db.add(audience_admin)
        created_notification = notification
    else:
        item.published_at = None
        item.expires_at = None

    db.add(
        MarketInsightReview(
            market_insight_id=item.id,
            reviewer_id=current_user.id,
            review_status=request.status.value,
            review_notes=request.review_notes,
            reviewed_at=datetime.utcnow(),
        )
    )

    return created_notification


@router.get("", response_model=list[InsightResponse])
async def list_insights(
    status: Optional[InsightStatus] = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """
    Fetch all market insights for admin review.
    Path: /api/v1/admin/insights
    """
    query = db.query(Insight)

    if status:
        query = query.filter(Insight.status == status)

    return query.order_by(Insight.created_at.desc()).all()


@router.post("/status", response_model=InsightResponse)
async def update_insight_status(
    request: InsightStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Update insight status and record an admin review.
    Path: /api/v1/admin/insights/status
    """
    entity_uuid = _parse_insight_uuid(request.entity_id)
    item = db.query(Insight).filter(Insight.id == entity_uuid).first()

    if not item:
        raise HTTPException(status_code=404, detail="Insight not found")

    notification = _apply_status_update(item=item, request=request, current_user=current_user, db=db)
    db.commit()
    db.refresh(item)

    if notification:
        db.refresh(notification)
        payload = json.dumps({
            "type": "NEW_NOTIFICATION",
            "data": {
                "id": notification.id,
                "title": notification.title,
                "message": notification.message
            }
        })
        await manager.broadcast(payload)

    return item


@router.post("/sync", status_code=200)
async def trigger_insights_sync(
    mode: str = Query(default="daily"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    """
    Manually trigger daily/weekly insights sync from ML API.
    Path: /api/v1/admin/insights/sync
    """
    if mode not in ["daily", "weekly"]:
        raise HTTPException(status_code=400, detail="Invalid sync mode. Must be 'daily' or 'weekly'")
    
    try:
        from app.services.insights_sync_service import sync_insights
        count = await sync_insights(db, mode=mode)
        db.commit()
        return {"message": f"Successfully synced {count} insights for mode {mode}"}
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync insights: {str(exc)}"
        ) from exc

