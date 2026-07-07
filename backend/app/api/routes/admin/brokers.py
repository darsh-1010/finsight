import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.brokers import Broker
from app.models.users import User
from app.schemas.brokers import BrokerCreate, BrokerResponse, BrokerUpdate
from app.services.audit_service import AuditService

router = APIRouter(prefix="/brokers", tags=["Admin Brokers"])


@router.post("/", response_model=BrokerResponse)
async def create_broker(
    broker: BrokerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    new_broker = Broker(**broker.dict())
    db.add(new_broker)
    db.commit()
    db.refresh(new_broker)

    AuditService.log_event(
        db=db,
        user_id=current_user.id,
        event_type="broker_created",
        entity_type="broker",
        action="create",
        entity_id=new_broker.id,
        metadata={"name": new_broker.name, "redirect_url": new_broker.redirect_url},
    )

    return new_broker


@router.post("/upload")
async def upload_brokers_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a CSV file.",
        )

    content = await file.read()
    decoded_content = content.decode("utf-8")
    csv_reader = csv.DictReader(io.StringIO(decoded_content))

    brokers_to_add = []
    errors = []
    row_num = 1

    # Validate headers
    if (
        not csv_reader.fieldnames
        or "name" not in csv_reader.fieldnames
        or "redirect_url" not in csv_reader.fieldnames
    ):
        raise HTTPException(
            status_code=400,
            detail="CSV must contain 'name' and 'redirect_url' columns.",
        )

    for row in csv_reader:
        row_num += 1
        name = row.get("name")
        redirect_url = row.get("redirect_url")

        if not name or not redirect_url:
            errors.append(
                f"Row {row_num}: Missing name or redirect_url",
            )
            continue

        brokers_to_add.append(
            Broker(name=name, redirect_url=redirect_url),
        )

    if errors:
        return {
            "message": "Upload completed with errors",
            "errors": errors,
            "added_count": 0,
        }

    if brokers_to_add:
        db.add_all(brokers_to_add)
        db.commit()

        AuditService.log_event(
            db=db,
            user_id=current_user.id,
            event_type="brokers_csv_uploaded",
            entity_type="broker",
            action="bulk_create",
            metadata={"added_count": len(brokers_to_add)},
        )

    return {
        "message": "Brokers uploaded successfully",
        "count": len(brokers_to_add),
    }


@router.get("/", response_model=list[BrokerResponse])
async def get_brokers(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    return db.query(Broker).all()


@router.put("/{broker_id}", response_model=BrokerResponse)
async def update_broker(
    broker_id: int,
    broker: BrokerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    db_broker = db.query(Broker).filter(Broker.id == broker_id).first()
    if not db_broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    update_data = broker.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_broker, key, value)

    db.commit()
    db.refresh(db_broker)

    AuditService.log_event(
        db=db,
        user_id=current_user.id,
        event_type="broker_updated",
        entity_type="broker",
        action="update",
        entity_id=db_broker.id,
        metadata=update_data,
    )

    return db_broker


@router.delete("/{broker_id}")
async def delete_broker(
    broker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    db_broker = db.query(Broker).filter(Broker.id == broker_id).first()
    if not db_broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    broker_name = db_broker.name
    db.delete(db_broker)
    db.commit()

    AuditService.log_event(
        db=db,
        user_id=current_user.id,
        event_type="broker_deleted",
        entity_type="broker",
        action="delete",
        entity_id=broker_id,
        metadata={"name": broker_name},
    )

    return {"message": "Broker deleted successfully"}
