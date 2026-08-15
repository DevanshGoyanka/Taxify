from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime


PAN_PATTERN = r"^[A-Z]{3}[PCHFATBLJG][A-Z][0-9]{4}[A-Z]$"


class ClientBase(BaseModel):
    pan: str = Field(..., min_length=10, max_length=10, pattern=PAN_PATTERN)
    # ``name`` is the derived full name.  It is optional at input time —
    # if blank, it is derived from first_name/middle_name/surname.  This
    # lets the Add Client form submit 3 name parts without duplicating the
    # full name in the payload.
    name: str = Field(default="", max_length=255)
    first_name: str = Field(default="", max_length=25)
    middle_name: str = Field(default="", max_length=25)
    surname: str = Field(default="", max_length=75)
    email: Optional[str] = None
    mobile: Optional[str] = None
    aadhaar: Optional[str] = None
    dob: Optional[str] = None

    @field_validator("pan", mode="before")
    @classmethod
    def normalize_pan(cls, value: object) -> object:
        """Normalize PAN before pattern validation and persistence."""
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", "first_name", "middle_name", "surname", mode="before")
    @classmethod
    def normalize_name_parts(cls, value: object) -> object:
        """Strip whitespace from each name part."""
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def derive_name_from_parts(self) -> "ClientBase":
        """Derive the full ``name`` from the three name parts.

        ``surname`` is the mandatory CBDT name field.  When the caller
        supplies name parts but leaves ``name`` blank, derive it.  When
        the caller supplies only ``name`` (legacy path), leave the parts
        empty — the ITR hydration will split it.  Raises if neither
        ``name`` nor ``surname`` is provided.
        """
        if not self.name and (self.first_name or self.middle_name or self.surname):
            self.name = " ".join(
                part for part in (self.first_name, self.middle_name, self.surname) if part
            )
        if not self.name and not self.surname:
            raise ValueError("Either name or surname must be provided")
        return self

class ClientCreate(ClientBase):
    portal_password: Optional[str] = None

class ClientUpdate(BaseModel):
    pan: Optional[str] = Field(default=None, min_length=10, max_length=10, pattern=PAN_PATTERN)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    first_name: Optional[str] = Field(default=None, max_length=25)
    middle_name: Optional[str] = Field(default=None, max_length=25)
    surname: Optional[str] = Field(default=None, max_length=75)
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

    @field_validator("name", "first_name", "middle_name", "surname", mode="before")
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
    firstName: str = Field(default="", validation_alias="first_name", serialization_alias="firstName")
    middleName: str = Field(default="", validation_alias="middle_name", serialization_alias="middleName")
    surname: str = Field(default="", validation_alias="surname", serialization_alias="surname")
    email: Optional[str] = None
    mobile: Optional[str] = None
    aadhaar: Optional[str] = None
    dob: Optional[str] = None
    archived: bool = False
    archivedAt: Optional[datetime] = None
    years: List[ClientYearResponse] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
