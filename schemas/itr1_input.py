from pydantic import BaseModel, Field
from typing import List, Optional

class TaxpayerInfo(BaseModel):
    pan: str = Field(..., description="Permanent Account Number")
    name: str
    ay: int = Field(..., description="Assessment Year, e.g., 2024")
    age: Optional[int] = None
    residential_status: Optional[str] = None

class SalaryIncome(BaseModel):
    gross_salary: float
    exemptions: float = 0.0
    deductions: float = 0.0

class HousePropertyIncome(BaseModel):
    annual_value: float
    municipal_taxes: float = 0.0
    self_occupied: bool = True
    interest_on_loan: float = 0.0

class OtherIncome(BaseModel):
    interest: float = 0.0
    capital_gains: float = 0.0
    others: float = 0.0

class Deductions(BaseModel):
    section_80c: float = 0.0
    section_80d: float = 0.0
    section_80e: float = 0.0
    section_80g: float = 0.0
    section_80u: float = 0.0
    hra_exemption: float = 0.0
    other: float = 0.0

class ITR1Input(BaseModel):
    taxpayer: TaxpayerInfo
    salary: SalaryIncome
    house_property: Optional[HousePropertyIncome] = None
    other_income: Optional[OtherIncome] = None
    deductions: Optional[Deductions] = None
    tax_paid: float = 0.0
    tax_due: Optional[float] = None
