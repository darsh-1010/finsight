from typing import Optional
from pydantic import BaseModel

class BrokerBase(BaseModel):
    name: str
    redirect_url: str

class BrokerCreate(BrokerBase):
    pass

class BrokerUpdate(BaseModel):
    name: Optional[str] = None
    redirect_url: Optional[str] = None

class BrokerResponse(BrokerBase):
    id: int

    class Config:
        from_attributes = True
        from_attributes = True
