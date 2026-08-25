"""ERI Digest service — the single canonical source of the ITR JSON Digest.

This module is the ONLY place in Taxify that computes the ``Digest`` value
stamped in ``CreationInfo.Digest``. Per the ERI onboarding SOP
("Digest_generation_ERI 2 (2).pdf" §5.3) and the Dual-Mode ERI Integration
Plan §3/§A2, the Digest MUST be computed strictly by the ERI flow, using
the secret key + iteration count for the active ``(ERI_MODE, ERI_ENV)``
credential bundle. There is no other Digest computation path and no
non-ERI source for these credentials.

Why this module exists separately from ``app.engine.itd.common``:
the JSON *file export* (``app/eri/type3/json_exporter.py``) MUST write
exactly the bytes that were hashed, or the portal's integrity check
fails. Previously the digest was computed over a char-by-char minified
string while the export used ``json.dumps(..., separators=(',',':'))`` —
two separate minification implementations that could silently diverge.
This module exposes ONE canonical serializer used by BOTH the digest
computation and the file export, eliminating the duplicated generation
path.

Reference flow (PDF §5.3), implemented step-by-step in
:func:`compute_digest`:

  Step 1. Read the input JSON (a ``dict``).
  Step 2. Minify the JSON — sort keys and remove all interstitial
          whitespace that is not part of a variable value.
  Step 3. Locate the ``Digest`` field and replace its value with the
          placeholder ``"-"``.
  Step 4. Load the secret key + iteration count from the active ERI
          credential bundle (:func:`app.eri.config.get_eri_credentials`).
  Step 5. Generate the digest: HMAC-SHA256, initialized with the secret
          key, hash the modified JSON string, repeat for ``iterations``
          times, then Base64-encode the final hash.
  Step 6. Update the JSON — replace the placeholder with the new digest.

The ``SWCreatedBy``/``JSONCreatedBy`` in ``CreationInfo`` and the
``(secret_key, iterations)`` used here are resolved from the SAME
``(mode, environment)`` suffix, so the identity stamped in the JSON
always matches the credentials that produced the Digest.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from typing import Any

from app.eri.config import ERIConfigurationError, ERICredentials, get_eri_credentials

__all__ = [
    "ERIDigestError",
    "canonicial_digest_payload",
    "compute_digest",
    "digest_of_delivered_text",
    "serialize_for_upload",
    "verify_delivered_text",
]


# Regex that matches the ``"Digest":"<any value>"`` member inside the
# minified JSON text. Whitespace-tolerant in case the caller pre-formatted
# the JSON; after minification there is never any whitespace, so this is a
# strict superset that also handles the pre-minify form.
_DIGEST_FIELD_RE = re.compile(r'"Digest"\s*:\s*"[^"]*"')

# The schema-legal placeholder for the Digest field during computation.
# The official ITR schema's ``Digest`` pattern is ``-|.{44}``, so ``-`` is
# the canonical "not yet computed" marker used by the SOP §5.3 Step 3.
_PLACEHOLDER = "-"


class ERIDigestError(ERIConfigurationError):
    """Raised when the Digest cannot be computed from ERI credentials.

    Subclasses :class:`ERIConfigurationError` so callers that catch the
    broader "ERI credentials unavailable" condition also catch Digest
    failures. The Digest MUST always flow from the selected ERI credential
    bundle; a placeholder ``-`` Digest or a digest computed with the wrong
    secret would produce a JSON whose integrity cannot be verified by the
    ITD portal. This error surfaces misconfiguration loudly so generation
    fails instead of emitting an unverifiable JSON.
    """


def _resolve_creds() -> ERICredentials:
    """Resolve the active ERI credential bundle or raise ``ERIDigestError``.

    Imports :func:`app.eri.config.get_eri_credentials` dynamically (at call
    time) so test mocks that patch ``app.eri.config.get_eri_credentials``
    take effect uniformly across the SW_ID and Digest resolution paths.
    """
    from app.eri.config import get_eri_credentials
    try:
        return get_eri_credentials()
    except ERIConfigurationError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise ERIDigestError(
            f"Could not resolve ERI credentials for Digest computation: {exc}"
        ) from exc


def canonicial_digest_payload(itr_json: dict[str, Any]) -> str:
    """Return the canonical UTF-8 JSON text the Digest is computed over.

    This is the single canonical serialization used by BOTH the Digest
    computation (:func:`compute_digest`) and the file export
    (:func:`serialize_for_upload`). Using one serializer guarantees the
    bytes hashed are byte-identical to the bytes uploaded, so the
    portal's integrity check never mismatches due to formatting drift.

    The canonical form (per SOP §5.3 Steps 2-3) is: sorted keys, no
    interstitial whitespace, ASCII preserved (``ensure_ascii=False``),
    and the ``Digest`` value replaced with the placeholder ``"-"``.

    Args:
        itr_json: The full ITR JSON dict (with any current Digest value).

    Returns:
        The minified, key-sorted UTF-8 JSON text with ``Digest`` set to
        ``"-"`` — the exact payload fed to HMAC-SHA256.
    """
    # Step 1 + 2: serialize with sorted keys + no interstitial whitespace.
    # ``default=str`` keeps Decimal/date values stable across runs.
    minified = json.dumps(
        itr_json,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    # Step 3: replace the Digest value with the placeholder "-".
    return _DIGEST_FIELD_RE.sub(f'"Digest":"{_PLACEHOLDER}"', minified)


def compute_digest(itr_json: dict[str, Any]) -> str:
    """Compute the official ITR JSON Digest from the active ERI credentials.

    Implements the SOP §5.3 step-by-step flow:

      Step 1. Read the input JSON (the ``itr_json`` dict).
      Step 2. Minify (sorted keys, no interstitial whitespace).
      Step 3. Replace the ``Digest`` value with ``"-"``.
      Step 4. Load the secret key + iteration count from the active
              ``(ERI_MODE, ERI_ENV)`` ERI credential bundle.
      Step 5. HMAC-SHA256: initialize with the secret key, hash the
              modified JSON string, repeat ``iterations`` times, then
              Base64-encode the final hash.
      Step 6. (Caller's responsibility) update the JSON with the digest.

    Args:
        itr_json: The full ITR JSON dict.

    Returns:
        The 44-character Base64-encoded Digest.

    Raises:
        ERIDigestError: If the active ERI credential bundle cannot be
            resolved or has no digest secret. The Digest MUST flow from
            the selected ERI credentials; a placeholder or secret-less
            digest is never returned.
    """
    creds = _resolve_creds()
    secret_key = creds.digest_secret_key
    if not secret_key:
        raise ERIDigestError(
            f"ERI_DIGEST_SECRET_KEY_{creds.mode.upper()}_"
            f"{creds.environment.upper()} is not set. The Digest must be "
            "computed with the secret for the selected ERI type; a "
            "placeholder Digest is not permitted."
        )
    iterations = int(creds.digest_iterations or 1)

    # Steps 1-3: the canonical payload the portal will also see.
    payload_text = canonicial_digest_payload(itr_json)

    # Step 5: iterated HMAC-SHA256 over the UTF-8 bytes, then Base64.
    return _hmac_loop(payload_text, secret_key, iterations)


def _hmac_loop(payload_text: str, secret_key: str, iterations: int) -> str:
    """Run SOP §5.3 Step 5: iterated HMAC-SHA256, then Base64-encode.

    The secret key seeds every round; each round hashes the previous round's
    raw digest bytes (the first round hashes the payload text).
    """
    key_bytes = secret_key.encode("utf-8")
    digest_bytes = payload_text.encode("utf-8")
    for _ in range(iterations):
        digest_bytes = hmac.new(key_bytes, digest_bytes, hashlib.sha256).digest()
    return base64.b64encode(digest_bytes).decode("utf-8")


def digest_of_delivered_text(json_text: str) -> str:
    """Recompute the Digest from a finished JSON file's own text.

    :func:`compute_digest` hashes a dict we still control. This hashes the
    bytes we actually hand over, following SOP §5.3 exactly as the ITD side
    would: minify the delivered text (key order preserved as written), swap
    the ``Digest`` value for ``"-"``, then run the iterated HMAC.

    Use it to prove a written ``.json`` file verifies. If the file was saved
    with indentation, minifying it here reproduces the ITD-side string, which
    will NOT match a Digest computed over the sorted-key canonical form — so
    this catches formatting drift between generation and export, which is the
    exact failure the ERI Helpdesk reports as a whitespace/formatting problem.

    Args:
        json_text: The complete text of a generated ITR JSON file.

    Returns:
        The 44-character Base64 Digest implied by that text.

    Raises:
        ERIDigestError: If the ERI credentials or digest secret are unavailable.
        ValueError: If ``json_text`` is not valid JSON.
    """
    creds = _resolve_creds()
    secret_key = creds.digest_secret_key
    if not secret_key:
        raise ERIDigestError(
            f"ERI_DIGEST_SECRET_KEY_{creds.mode.upper()}_"
            f"{creds.environment.upper()} is not set; the delivered JSON's "
            "Digest cannot be verified."
        )
    # SOP Step 2: minify. json.loads preserves member order, so this is the
    # delivered file's own ordering, not our canonical sorted ordering.
    minified = json.dumps(
        json.loads(json_text), ensure_ascii=False, separators=(",", ":")
    )
    # SOP Step 3: placeholder the Digest.
    payload_text = _DIGEST_FIELD_RE.sub(f'"Digest":"{_PLACEHOLDER}"', minified)
    return _hmac_loop(payload_text, secret_key, int(creds.digest_iterations or 1))


def verify_delivered_text(json_text: str) -> bool:
    """Return True if the Digest inside ``json_text`` matches its own bytes.

    This is the check to run on a file before emailing it to
    ``erihelp@incometax.gov.in`` or uploading it to the portal.
    """
    match = re.search(r'"Digest"\s*:\s*"([^"]*)"', json_text)
    if not match:
        return False
    stamped = match.group(1)
    if stamped == _PLACEHOLDER or len(stamped) != 44:
        return False
    return stamped == digest_of_delivered_text(json_text)


def serialize_for_upload(itr_json: dict[str, Any], digest: str | None = None) -> str:
    """Return the exact UTF-8 JSON text to upload to the ITD portal.

    This serializer is the counterpart of :func:`canonicial_digest_payload`:
    it produces the same sorted-key, whitespace-free form, but stamps the
    computed ``digest`` into the ``Digest`` field instead of the
    placeholder. Because both use the identical serialization parameters,
    the bytes uploaded match the bytes hashed (with only the ``Digest``
    value differing from ``"-"`` to the computed digest) — exactly the
    SOP §5.3 Step 6 "update JSON" transformation.

    Args:
        itr_json: The full ITR JSON dict.
        digest: The computed 44-character Digest. If provided, it is
            stamped into the ``Digest`` field. If ``None``, the existing
            ``Digest`` value in ``itr_json`` is left untouched (used when
            re-serializing an already-digested JSON for upload).

    Returns:
        The canonical UTF-8 JSON text for upload.

    Raises:
        ERIDigestError: If ``digest`` is provided but is not a valid
            44-character Base64 string (never ``"-"``). This prevents a
            placeholder Digest from ever leaving Taxify.
    """
    if digest is not None:
        if not isinstance(digest, str) or digest == _PLACEHOLDER or len(digest) != 44:
            raise ERIDigestError(
                "A placeholder or malformed Digest cannot be serialized for "
                "upload. The Digest must be a 44-character Base64 string "
                "computed from the active ERI credentials."
            )
        # Stamp the computed digest into a copy so the caller's dict is
        # not mutated; the upload text must carry the real digest.
        stamped = _DIGEST_FIELD_RE.sub(
            f'"Digest":"{digest}"',
            json.dumps(
                itr_json,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
                separators=(",", ":"),
            ),
        )
        return stamped
    # No digest supplied: serialize as-is (the dict already carries the
    # computed digest in its CreationInfo.Digest field).
    return json.dumps(
        itr_json,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
