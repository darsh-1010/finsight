from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db
from app.models.notifications import (
    AudienceType,
    Notification,
    NotificationAudience,
    UserNotificationRead,
)
from app.models.users import User
from app.schemas.notifications import NotificationReadResponse, NotificationResponse

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


def _user_audience_filters(user: User):
    filters = [
        NotificationAudience.audience_type == AudienceType.ALL,
        and_(
            NotificationAudience.audience_type == AudienceType.USER,
            NotificationAudience.audience_id == str(user.id),
        ),
    ]

    if user.role and user.role.role == "admin":
        filters.append(NotificationAudience.audience_type == AudienceType.ADMIN)

    if user.subscription and user.subscription.tier:
        tier_values = {
            str(user.subscription.tier_id),
            str(user.subscription.tier.level),
        }
        filters.append(
            and_(
                NotificationAudience.audience_type == AudienceType.TIER,
                NotificationAudience.audience_id.in_(tier_values),
            )
        )

    return filters


def _base_visible_notifications_query(db: Session, user: User):
    now = datetime.now(timezone.utc)

    return (
        db.query(Notification)
        .join(NotificationAudience)
        .options(joinedload(Notification.audiences))
        .filter(or_(*_user_audience_filters(user)))
        .filter(or_(Notification.expires_at.is_(None), Notification.expires_at > now))
    )


def _serialize_notification(
    notification: Notification,
    read_ids: set[int],
) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        title=notification.title,
        message=notification.message,
        notification_type=notification.notification_type,
        entity_type=notification.entity_type,
        entity_id=notification.entity_id,
        priority=notification.priority,
        action_url=notification.action_url,
        created_by=notification.created_by,
        created_at=notification.created_at,
        expires_at=notification.expires_at,
        is_read=notification.id in read_ids,
        audience_types=[audience.audience_type for audience in notification.audiences],
    )


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notifications = (
        _base_visible_notifications_query(db, user)
        .order_by(Notification.created_at.desc())
        .distinct()
        .limit(limit)
        .all()
    )

    if not notifications:
        return []

    notification_ids = [item.id for item in notifications]
    reads = (
        db.query(UserNotificationRead.notification_id)
        .filter(
            UserNotificationRead.user_id == user.id,
            UserNotificationRead.notification_id.in_(notification_ids),
            UserNotificationRead.is_read.is_(True),
        )
        .all()
    )
    read_ids = {row.notification_id for row in reads}

    serialized = [
        _serialize_notification(notification, read_ids)
        for notification in notifications
    ]

    if unread_only:
        return [notification for notification in serialized if not notification.is_read]

    return serialized


@router.post("/{notification_id}/read", response_model=NotificationReadResponse)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notification = (
        _base_visible_notifications_query(db, user)
        .filter(Notification.id == notification_id)
        .first()
    )

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    read = (
        db.query(UserNotificationRead)
        .filter(
            UserNotificationRead.notification_id == notification_id,
            UserNotificationRead.user_id == user.id,
        )
        .first()
    )
    now = datetime.now(timezone.utc)

    if read:
        read.is_read = True
        read.read_at = now
    else:
        read = UserNotificationRead(
            notification_id=notification_id,
            user_id=user.id,
            is_read=True,
            read_at=now,
        )
        db.add(read)

    db.commit()
    db.refresh(read)

    return NotificationReadResponse(
        id=read.id,
        notification_id=read.notification_id,
        is_read=read.is_read,
        read_at=read.read_at,
    )
