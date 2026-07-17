from pydantic import BaseModel, Field
from typing import Optional

class TaxpayerInfo(BaseModel):
    pan: str = Field(..., description="Permanent Account Number")
    name: str
    ay: int = Field(..., description="Assessment Year, e.g., 2024")
    age: Optional[int] = None
    residential_status: Optional[str] = None

class BusinessIncome(BaseModel):
    presumptive_code: str = Field(..., description="44AD, 44ADA, or 44AE")
    gross_receipts: float
    allowable_expenses: float
    net_profit: float

class SalaryIncome(BaseModel):
    gross_salary: float
    exemptions: float = 0.0

class HousePropertyIncome(BaseModel):
    annual_value: float
    municipal_taxes: float = 0.0
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
    other: float = 0.0

class ITR4Input(BaseModel):
    taxpayer: TaxpayerInfo
    business: BusinessIncome
    salary: Optional[SalaryIncome] = None
    house_property: Optional[HousePropertyIncome] = None
    other_income: Optional[OtherIncome] = None
    deductions: Optional[Deductions] = None
    tax_paid: float = 0.0
