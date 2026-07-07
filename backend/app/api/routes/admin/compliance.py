
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.compliance import ComplianceDisclosure, ComplianceGroup
from app.schemas.compliance import (
    ComplianceDisclosureCreate,
    ComplianceDisclosureResponse,
    ComplianceDisclosureUpdate,
    ComplianceGroupCreate,
    ComplianceGroupResponse,
)

router = APIRouter(prefix="/compliance", tags=["Admin Compliance"])


# --- Groups ---


@router.post("/groups", response_model=ComplianceGroupResponse)
async def create_compliance_group(
    group: ComplianceGroupCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    """Create a new compliance group."""
    existing_group = (
        db.query(ComplianceGroup).filter(ComplianceGroup.key == group.key).first()
    )
    if existing_group:
        raise HTTPException(
            status_code=400,
            detail="Group with this key already exists",
        )

    new_group = ComplianceGroup(**group.dict())
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    return new_group


@router.get("/groups", response_model=list[ComplianceGroupResponse])
async def get_compliance_groups(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    """List all compliance groups."""
    return db.query(ComplianceGroup).all()


@router.delete("/groups/{group_id}")
async def delete_compliance_group(
    group_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    """Delete a compliance group and its disclosures."""
    db_group = db.query(ComplianceGroup).filter(ComplianceGroup.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Delete associated disclosures first to avoid FK violations
    (
        db.query(ComplianceDisclosure)
        .filter(ComplianceDisclosure.group_id == group_id)
        .delete()
    )

    db.delete(db_group)
    db.commit()
    return {"message": "Group deleted successfully"}


# --- Disclosures ---


@router.post("/disclosures", response_model=ComplianceDisclosureResponse)
async def create_disclosure(
    disclosure: ComplianceDisclosureCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    """Create a new disclosure in a group."""
    new_disclosure = ComplianceDisclosure(**disclosure.dict())
    db.add(new_disclosure)
    db.commit()
    db.refresh(new_disclosure)
    return new_disclosure


@router.put("/disclosures/{disclosure_id}", response_model=ComplianceDisclosureResponse)
async def update_disclosure(
    disclosure_id: int,
    disclosure: ComplianceDisclosureUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    """Update an existing disclosure."""
    db_disclosure = (
        db.query(ComplianceDisclosure)
        .filter(ComplianceDisclosure.id == disclosure_id)
        .first()
    )
    if not db_disclosure:
        raise HTTPException(status_code=404, detail="Disclosure not found")

    update_data = disclosure.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_disclosure, key, value)

    db.commit()
    db.refresh(db_disclosure)
    return db_disclosure


@router.delete("/disclosures/{disclosure_id}")
async def delete_disclosure(
    disclosure_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    """Delete a disclosure."""
    db_disclosure = (
        db.query(ComplianceDisclosure)
        .filter(ComplianceDisclosure.id == disclosure_id)
        .first()
    )
    if not db_disclosure:
        raise HTTPException(status_code=404, detail="Disclosure not found")

    db.delete(db_disclosure)
    db.commit()
    return {"message": "Disclosure deleted successfully"}
