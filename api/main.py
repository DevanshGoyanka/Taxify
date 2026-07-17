from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import json

from schemas import ITR1Input, ITR4Input
from api.services.prefill_service import (
    map_26as_to_prefill,
    map_ais_to_prefill,
    prefill_to_itr1_input,
    PrefillData
)

app = FastAPI(
    title=\"Taxify API\",
    description=\"Indian Income Tax Return Computation and Filing API\",
    version=\"0.1.0\"
)

# Placeholder for tax computation engine
def compute_tax_it_r1(data: ITR1Input) -> dict:
    # TODO: Implement actual tax calculation
    gross_income = data.salary.gross_salary
    exemptions = data.salary.exemptions
    deductions = data.salary.deductions
    
    taxable_salary = max(0, gross_income - exemptions - deductions)
    
    # Placeholder calculation
    tax = 0
    if taxable_salary > 250000:
        tax = (taxable_salary - 250000) * 0.05
    
    return {
        \"gross_income\": gross_income,
        \"taxable_income\": taxable_salary,
        \"tax\": tax,
        \"status\": \"computed\"
    }

def compute_tax_it_r4(data: ITR4Input) -> dict:
    # TODO: Implement actual tax calculation for presumptive income
    gross_income = data.business.net_profit
    tax = 0
    if gross_income > 250000:
        tax = (gross_income - 250000) * 0.05
    
    return {
        \"gross_income\": gross_income,
        \"taxable_income\": gross_income,
        \"tax\": tax,
        \"status\": \"computed\"
    }

# Route: Compute tax
@app.post(\"/compute/itr1\")
def compute_itr1(data: ITR1Input):
    try:
        result = compute_tax_it_r1(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post(\"/compute/itr4\")
def compute_itr4(data: ITR4Input):
    try:
        result = compute_tax_it_r4(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Route: Validate input data
@app.post(\"/validate/itr1\")
def validate_itr1(data: ITR1Input):
    try:
        # Pydantic already validates on input, so just return success
        return {\"valid\": True, \"message\": \"ITR-1 data is valid\"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post(\"/validate/itr4\")
def validate_itr4(data: ITR4Input):
    try:
        return {\"valid\": True, \"message\": \"ITR-4 data is valid\"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Route: Generate JSON for ITD utility
@app.post(\"/generate-json/itr1\")
def generate_json_itr1(data: ITR1Input):
    # TODO: Implement actual JSON generation aligned with CBDT schema
    try:
        json_output = {
            \"form\": \"ITR-1\",
            \"assessment_year\": data.taxpayer.ay,
            \"pan\": data.taxpayer.pan,
            \"taxpayer_name\": data.taxpayer.name,
            # Add more fields as needed for ITD utility
        }
        return {\"json\": json_output, \"status\": \"generated\"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post(\"/generate-json/itr4\")
def generate_json_itr4(data: ITR4Input):
    # TODO: Implement actual JSON generation for ITR-4
    try:
        json_output = {
            \"form\": \"ITR-4\",
            \"assessment_year\": data.taxpayer.ay,
            \"pan\": data.taxpayer.pan,
            \"taxpayer_name\": data.taxpayer.name,
        }
        return {\"json\": json_output, \"status\": \"generated\"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Route: Prefill data from 26AS/AIS
@app.get(\"/prefill/{pan}\")
def prefill_data(pan: str):
    \"\"\"
    Get prefill data for a PAN.
    In production, this would fetch from downloaded 26AS/AIS files.
    Currently returns mock data for testing.
    \"\"\"
    # TODO: Replace with actual 26AS/AIS fetch from automation
    mock_26as_data = {
        \"pan\": pan,
        \"salary\": {\"gross\": 500000.0, \"tds\": 25000.0},
        \"house_property\": {\"income\": 0.0},
        \"interest\": {\"income\": 10000.0},
        \"capital_gains\": {\"income\": 0.0},
        \"other\": {\"income\": 0.0},
        \"tds\": {\"total\": 25000.0},
    }
    
    prefill = map_26as_to_prefill(mock_26as_data)
    itr1_input = prefill_to_itr1_input(prefill)
    
    return {
        \"pan\": pan,
        \"prefill_data\": prefill.model_dump(),
        \"itr1_input\": itr1_input,
    }

# Route: Import 26AS data
@app.post(\"/import/26as\")
def import_26as(data: dict):
    \"\"\"
    Import 26AS data. Expects dict with 26AS fields.
    Maps to prefill schema and returns ITR1-compatible input.
    \"\"\"
    try:
        prefill = map_26as_to_prefill(data)
        itr1_input = prefill_to_itr1_input(prefill)
        return {
            \"status\": \"imported\",
            \"prefill\": prefill.model_dump(),
            \"itr1_input\": itr1_input,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Route: Import AIS data
@app.post(\"/import/ais\")
def import_ais(data: dict):
    \"\"\"
    Import AIS data. Expects dict with AIS fields.
    Maps to prefill schema and returns ITR1-compatible input.
    \"\"\"
    try:
        prefill = map_ais_to_prefill(data)
        itr1_input = prefill_to_itr1_input(prefill)
        return {
            \"status\": \"imported\",
            \"prefill\": prefill.model_dump(),
            \"itr1_input\": itr1_input,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Route: Submit return via portal automation
@app.post(\"/submit\")
async def submit_return(submission_data: dict):
    \"\"\"
    Submit ITR via portal automation.
    Requires: user_id, password, itr_json
    \"\"\"
    try:
        from api.services.submission_service import SubmissionService
        
        user_id = submission_data.get(\"user_id\")
        password = submission_data.get(\"password\")
        itr_json = submission_data.get(\"itr_json\")
        
        if not user_id or not password or not itr_json:
            raise HTTPException(
                status_code=400,
                detail=\"Missing required fields: user_id, password, itr_json\"
            )
        
        service = SubmissionService()
        await service.init_browser(headless=False)
        
        # Login
        await service.login(user_id, password)
        
        # Submit ITR
        result = await service.submit_itr(itr_json)
        
        await service.close()
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Route: Submit Aadhaar OTP for e-verification
@app.post(\"/submit/verify-otp\")
async def verify_otp(data: dict):
    \"\"\"Submit Aadhaar OTP for e-verification.\"\"\"
    try:
        from api.services.submission_service import SubmissionService
        
        otp = data.get(\"otp\")
        if not otp:
            raise HTTPException(status_code=400, detail=\"Missing OTP\")
        
        # This would need to be wired to an active session
        return {\"status\": \"pending\", \"message\": \"OTP verification requires active session\"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check
@app.get(\"/health\")
def health_check():
    return {\"status\": \"healthy\"}
