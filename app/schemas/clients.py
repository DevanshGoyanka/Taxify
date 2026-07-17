from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ClientBase(BaseModel):
    pan: str = Field(..., max_length=10)
    name: str = Field(..., max_length=255)
    email: Optional[str] = None
    mobile: Optional[str] = None
    aadhaar: Optional[str] = None
    dob: Optional[str] = None

class ClientCreate(ClientBase):
    portal_password: Optional[str] = None

class ClientUpdate(BaseModel):
    pan: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    aadhaar: Optional[str] = None
    dob: Optional[str] = None
    portal_password: Optional[str] = None

class ClientYearResponse(BaseModel):
    year: str
    itrType: str
    status: str

    class Config:
        from_attributes = True

class ClientResponse(BaseModel):
    id: int
    pan: str
    name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    aadhaar: Optional[str] = None
    dob: Optional[str] = None
    years: List[ClientYearResponse] = []
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True
