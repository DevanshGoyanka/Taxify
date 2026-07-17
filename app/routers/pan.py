from fastapi import APIRouter
from app.routers.clients import parse_pan

router = APIRouter(prefix="/pan", tags=["pan"])

@router.get("/{pan}/validate")
def validate_pan(pan: str):
    res = parse_pan(pan)
    return {"pan": pan, "valid": res["valid"], "message": "PAN is valid" if res["valid"] else "Invalid PAN format"}

@router.get("/{pan}/analyze")
def analyze_pan(pan: str):
    return parse_pan(pan)
