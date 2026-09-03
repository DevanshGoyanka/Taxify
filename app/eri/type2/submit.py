from typing import Any, Dict, Optional

import requests

from app.eri.config import get_eri_base_url, get_eri_user_id
from app.eri.envelope import build_request_envelope, eri_headers, parse_response_envelope
from app.eri.exceptions import ERIApiError
from app.eri.type2.validate import build_itr_payload


def submit_itr(
    pan: str,
    form_name: str,
    form_code: str,
    ay: str,
    filing_type_cd: str,
    filing_mode: str,
    income_tax_sec_cd: str,
    submitted_by: str,
    form_data_json: str,
    auth_token: str,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Validates and submits an ITR to the eFiling system.

    Cites: Docs/API_SubmitFlow_v1.1.pdf Section 4 (submitItr API) -- same
    request/response shape as validateItr (see ``validate.py``), differing
    only in ``serviceName`` ("EriItrSubmit") and the URL path ("/submit").
    A successful call assigns ``arnNumber``, which validateItr never does.
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")

    payload = build_itr_payload(
        pan=pan,
        form_name=form_name,
        form_code=form_code,
        ay=ay,
        filing_type_cd=filing_type_cd,
        filing_mode=filing_mode,
        income_tax_sec_cd=income_tax_sec_cd,
        submitted_by=submitted_by,
        form_data_json=form_data_json,
        created_by=created_by,
        service_name="EriItrSubmit",
    )

    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)

    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/submit",
        json=envelope,
        headers=headers,
        verify=True,
        timeout=120.0,
    )

    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")

    return parse_response_envelope(response.json())
