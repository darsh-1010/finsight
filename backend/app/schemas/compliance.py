from datetime import datetime

from pydantic import BaseModel

from app.models.compliance import DisclosureType


class ComplianceDisclosureBase(BaseModel):
    title: str
    content: str
    disclosure_type: DisclosureType
    icon_name: str
    color: str | None = None
    sort_order: int = 0
    is_active: bool = True


class ComplianceDisclosureCreate(ComplianceDisclosureBase):
    group_id: int


class ComplianceDisclosureUpdate(ComplianceDisclosureBase):
    pass


class ComplianceDisclosureResponse(ComplianceDisclosureBase):
    id: int
    group_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComplianceGroupBase(BaseModel):
    name: str
    key: str
    description: str | None = None


class ComplianceGroupCreate(ComplianceGroupBase):
    pass


class ComplianceGroupResponse(ComplianceGroupBase):
    id: int
    created_at: datetime
    updated_at: datetime
    disclosures: list[ComplianceDisclosureResponse] = []

    class Config:
        from_attributes = True
