"""ITR Life Cycle Status (EriITRLifeCycleStatus).

Ad hoc client for a Type-2 endpoint not implemented elsewhere in this project --
added for exploratory live testing only, not part of the standard
login/validate/submit/e-verify/acknowledgement filing pipeline.

Cites: Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/
View+ITR+lifecycle_2.0 (3).pdf, Section 4 (ITRLifeCycleStatus API Details).
"""
import requests
from datetime import datetime, timedelta
from typing import Any, Dict

from app.eri.config import get_eri_base_url, get_eri_user_id
from app.eri.envelope import build_request_envelope, eri_headers, parse_response_envelope
from app.eri.exceptions import ERIApiError


def get_ist_timestamp() -> str:
    ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return ist_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def get_itr_lifecycle_status(pan: str, ay: str, auth_token: str) -> Dict[str, Any]:
    """Fetches the full lifecycle status (filing/verification/processing
    activity timeline) for every ITR filed by this PAN for the given
    assessment year.

    Args:
        pan: Taxpayer PAN.
        ay: Assessment year, 4-digit plain format (e.g. "2026"), matching
            the spec's own sample request (`"ay": "2021"`) and this
            codebase's existing `ay` convention for validate/submit.
        auth_token: Active Type-2 session auth token.

    Returns:
        Parsed response envelope: `itrLifeCycleData` (list, one entry per
        filed return for the AY), `successFlag`, `httpStatus`.
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")

    payload = {
        "serviceName": "EriITRLifeCycleStatus",
        "pan": pan,
        "ay": ay,
        "timeStamp": get_ist_timestamp(),
    }

    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)

    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/lifecycle",
        json=envelope,
        headers=headers,
        verify=True,
        timeout=120.0,
    )

    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")

    return parse_response_envelope(response.json())
