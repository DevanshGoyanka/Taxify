from typing import Optional
from pydantic import BaseModel

class PrefillData(BaseModel):
    pan: str
    salary_gross: float = 0.0
    salary_tds: float = 0.0
    house_property_income: float = 0.0
    interest_income: float = 0.0
    capital_gains: float = 0.0
    other_income: float = 0.0
    tds_26as_total: float = 0.0
    tax_credits: float = 0.0


def map_26as_to_prefill(data: dict) -> PrefillData:
    """
    Map 26AS data to prefill schema.
    Expected 26AS data structure from ITD portal:
    - 'salary': {'gross': float, 'tds': float}
    - 'house_property': {'income': float}
    - 'interest': {'income': float}
    - 'capital_gains': {'income': float}
    - 'other': {'income': float}
    - 'tds': {'total': float}
    """
    return PrefillData(
        pan=data.get('pan', ''),
        salary_gross=data.get('salary', {}).get('gross', 0.0),
        salary_tds=data.get('salary', {}).get('tds', 0.0),
        house_property_income=data.get('house_property', {}).get('income', 0.0),
        interest_income=data.get('interest', {}).get('income', 0.0),
        capital_gains=data.get('capital_gains', {}).get('income', 0.0),
        other_income=data.get('other', {}).get('income', 0.0),
        tds_26as_total=data.get('tds', {}).get('total', 0.0),
        tax_credits=data.get('tds', {}).get('total', 0.0),
    )


def map_ais_to_prefill(data: dict) -> PrefillData:
    """
    Map AIS data to prefill schema.
    Expected AIS data structure:
    - 'salary': {'amount': float}
    - 'house_property': {'income': float}
    - 'interest': {'amount': float}
    - 'capital_gains': {'short_term': float, 'long_term': float}
    - 'other_income': {'amount': float}
    - 'tds': {'total': float}
    """
    salary = data.get('salary', {})
    cap_gains = data.get('capital_gains', {})
    interest = data.get('interest', {})
    other = data.get('other_income', {})
    tds = data.get('tds', {})

    return PrefillData(
        pan=data.get('pan', ''),
        salary_gross=salary.get('amount', 0.0),
        salary_tds=tds.get('salary', 0.0),
        house_property_income=data.get('house_property', {}).get('income', 0.0),
        interest_income=interest.get('amount', 0.0),
        capital_gains=(cap_gains.get('short_term', 0.0) + cap_gains.get('long_term', 0.0)),
        other_income=other.get('amount', 0.0),
        tds_26as_total=tds.get('total', 0.0),
        tax_credits=tds.get('total', 0.0),
    )


def prefill_to_itr1_input(prefill: PrefillData) -> dict:
    """
    Convert prefill data to ITR1Input-compatible dict.
    This is what the frontend will receive for pre-filling forms.
    """
    return {
        "taxpayer": {
            "pan": prefill.pan,
            "name": prefill.pan,  # Will be filled from user profile
            "ay": 2025,  # Current AY
        },
        "salary": {
            "gross_salary": prefill.salary_gross,
            "exemptions": 0.0,
            "deductions": 0.0,
        },
        "house_property": {
            "annual_value": prefill.house_property_income,
            "municipal_taxes": 0.0,
            "self_occupied": True,
            "interest_on_loan": 0.0,
        } if prefill.house_property_income > 0 else None,
        "other_income": {
            "interest": prefill.interest_income,
            "capital_gains": prefill.capital_gains,
            "others": prefill.other_income,
        },
        "deductions": {
            "section_80c": 0.0,
            "section_80d": 0.0,
            "section_80e": 0.0,
            "section_80g": 0.0,
            "section_80u": 0.0,
            "hra_exemption": 0.0,
            "other": 0.0,
        },
        "tax_paid": prefill.tax_credits,
    }
