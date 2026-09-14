"""ITR Download (EriITRDownload).

Ad hoc client for a Type-2 endpoint not implemented elsewhere in this project --
added for exploratory live testing only, not part of the standard
login/validate/submit/e-verify/acknowledgement filing pipeline.

Cites: Reference Docs by CBDT & ITD/Official ERI REFERENCE Documentation/
View+ITR+lifecycle_2.0 (3).pdf, Section 5 (ITRDownload API Details).
"""
import requests
from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Union

from app.eri.config import get_eri_base_url, get_eri_user_id
from app.eri.envelope import build_request_envelope, eri_headers, parse_response_envelope
from app.eri.exceptions import ERIApiError


def get_ist_timestamp() -> str:
    ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return ist_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def download_itr(
    pan: str, ack_num: str, auth_token: str, fmt: Literal["PDF", "JSON"] = "PDF"
) -> Union[bytes, Dict[str, Any]]:
    """Downloads a previously-submitted ITR in PDF or JSON form.

    Per the spec's own sample response: on success, a PDF request returns a
    **password-protected** PDF binary body (password = PAN followed by
    DOB/DOI in DDMMYYYY format, not decrypted here), while a JSON request
    returns a JSON envelope `{"ITR": "<symmetric-key-encrypted string>"}`
    (not auto-decrypted here -- the caller is responsible for that, mirroring
    how `prefill.py::decrypt_prefill()` handles the analogous prefill payload,
    since this endpoint's own encryption scheme has not been independently
    confirmed to be identical).

    Args:
        pan: Taxpayer PAN.
        ack_num: Acknowledgement/ARN number of the submitted return.
        auth_token: Active Type-2 session auth token.
        fmt: "PDF" (default) or "JSON".

    Returns:
        Raw PDF bytes when `fmt="PDF"` and the response is a binary body;
        otherwise the parsed JSON response envelope.
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")

    payload = {
        "serviceName": "EriITRDownload",
        "pan": pan,
        "ackNum": ack_num,
        "format": fmt,
        "timeStamp": get_ist_timestamp(),
    }

    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)

    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/downloadItr",
        json=envelope,
        headers=headers,
        verify=True,
        timeout=120.0,
    )

    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")

    content_type = response.headers.get("Content-Type", "").lower()
    if fmt == "PDF" and "application/pdf" in content_type:
        return response.content
    if fmt == "PDF" and response.content[:5] == b"%PDF-":
        return response.content

    return parse_response_envelope(response.json())
