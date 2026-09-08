import base64
import json
import requests
from typing import Any, Dict, Optional

from app.eri.envelope import build_request_envelope, parse_response_envelope, eri_headers
from app.eri.exceptions import ERIApiError
from app.eri.type2.everify import get_ist_timestamp
from app.eri.config import get_eri_base_url, get_eri_user_id


def build_itr_payload(
    pan: str,
    form_name: str,
    form_code: str,
    ay: str,
    filing_type_cd: str,
    filing_mode: str,
    income_tax_sec_cd: str,
    submitted_by: str,
    form_data_json: str,
    created_by: Optional[str] = None,
    service_name: str = "EriValidateItr",
) -> Dict[str, Any]:
    """Builds the shared request-data payload for validateItr/submitItr.

    Cites: Docs/API_SubmitFlow_v1.1.pdf Section 4.4.2/4.4.3 -- request and
    response parameters are identical for both endpoints; only
    ``serviceName`` and the URL path differ (see ``validate_itr``/
    ``submit_itr`` below).

    ``form_data_json`` is the already-serialized CBDT ITD JSON string (the
    output of this form's ``app/engine/itd/itr{N}.py`` builder) -- this
    module does not build or validate ITR JSON itself, matching the existing
    ``app/eri/type2/*`` modules' style of taking already-prepared values
    rather than re-deriving filing business logic at the API-call layer.

    Empirically confirmed (2026-09-04, live UAT call): the live gateway
    rejects a plain JSON string for ``formData`` with
    errCd=EF500140 "Form data is not properly formatted, It should be in
    double-quotes and then Base-64 encoded" -- despite the spec PDF's own
    sample request showing an unencoded string. The real requirement is the
    JSON string, Base64-encoded, same as this project's other Base64-then-
    sign pattern elsewhere in the envelope. Do not "fix" this back to a
    plain string without re-verifying against a live call first.

    Also empirically confirmed the same session: sending ``form_data_json``
    re-serialized in its original (insertion) key order -- rather than the
    SORTED key order ``app/eri/digest.py::compute_digest()`` used to compute
    the JSON's own embedded ``CreationInfo.Digest`` -- gets rejected with
    errCd=Digest_Invalid "Modification to ITR details outside Utility is
    not allowed", even though the content is byte-for-byte identical and
    the digest is independently verifiable as correct offline. ITD's server
    re-serializes with sorted keys before recomputing the digest to compare,
    so an unsorted-but-content-identical payload doesn't match. To make this
    caller-proof (no caller has to remember this), this function re-parses
    ``form_data_json`` and re-serializes it canonically (sorted, whitespace-
    free) itself, regardless of how the caller originally produced it.
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")

    canonical_form_data = json.dumps(
        json.loads(form_data_json), sort_keys=True, separators=(",", ":")
    )
    form_data_b64 = base64.b64encode(canonical_form_data.encode("utf-8")).decode("ascii")

    return {
        "serviceName": service_name,
        "pan": pan,
        "header": {
            "formName": form_name,
            "formCode": form_code,
            "mimeType": "json",
            "entityNum": pan,
            "entityType": "p",
            "ay": ay,
            "createdBy": created_by or eri_user_id,
            "filingTypeCd": filing_type_cd,
            "filingMode": filing_mode,
            "incomeTaxSecCd": income_tax_sec_cd,
            "submittedBy": submitted_by,
        },
        "formData": form_data_b64,
        # Correction, confirmed directly by ITD via email (not shown in this
        # spec PDF's own sample request tables): every API call must carry a
        # timeStamp field inside the signed payload, matching login.py/
        # add_client.py/everify.py/prefill.py/acknowledgement.py's existing
        # pattern -- not an everify.py-only quirk as an earlier draft of this
        # module assumed.
        "timeStamp": get_ist_timestamp(),
    }


def validate_itr(
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
    """Validates an ITR without submitting it to the eFiling system.

    Cites: Docs/API_SubmitFlow_v1.1.pdf Section 4 (validateItr API).
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
        service_name="EriValidateItr",
    )

    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)

    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/validate",
        json=envelope,
        headers=headers,
        verify=True,
        timeout=120.0,
    )

    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")

    return parse_response_envelope(response.json())
