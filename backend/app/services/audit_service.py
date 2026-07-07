from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_logs import AuditLog


class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        user_id: int | None,
        event_type: str,
        entity_type: str,
        action: str,
        *,
        entity_id: Any | None = None,
        **extra: Any,
    ) -> AuditLog:
        """
        Create an audit log entry.
        """
        audit_log = AuditLog(
            user_id=user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            action=action,
            extra_metadata=extra.get("metadata"),
            ip_address=extra.get("ip_address"),
            user_agent=extra.get("user_agent"),
        )
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log
