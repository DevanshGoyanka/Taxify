from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from datetime import datetime


PAN_PATTERN = r"^[A-Z]{3}[PCHFATBLJG][A-Z][0-9]{4}[A-Z]$"


class ClientBase(BaseModel):
    pan: str = Field(..., min_length=10, max_length=10, pattern=PAN_PATTERN)
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    mobile: Optional[str] = None
    aadhaar: Optional[str] = None
    dob: Optional[str] = None

    @field_validator("pan", mode="before")
    @classmethod
    def normalize_pan(cls, value: object) -> object:
        """Normalize PAN before pattern validation and persistence."""
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """Remove surrounding whitespace from the client name."""
        return value.strip() if isinstance(value, str) else value

class ClientCreate(ClientBase):
    portal_password: Optional[str] = None

class ClientUpdate(BaseModel):
    pan: Optional[str] = Field(default=None, min_length=10, max_length=10, pattern=PAN_PATTERN)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[str] = None
    mobile: Optional[str] = None
    aadhaar: Optional[str] = None
    dob: Optional[str] = None
    portal_password: Optional[str] = None

    @field_validator("pan", mode="before")
    @classmethod
    def normalize_pan(cls, value: object) -> object:
        """Normalize an updated PAN before validation."""
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """Remove surrounding whitespace from an updated client name."""
        return value.strip() if isinstance(value, str) else value

class ClientYearResponse(BaseModel):
    year: str
    itrType: str
    status: str

    model_config = ConfigDict(from_attributes=True)

class ClientResponse(BaseModel):
    id: int
    publicId: str
    pan: str
    name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    aadhaar: Optional[str] = None
    dob: Optional[str] = None
    archived: bool = False
    archivedAt: Optional[datetime] = None
    years: List[ClientYearResponse] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)
