"""Foreground Type-3 filing test for an explicitly selected real client.

Safe default:
    Generate and validate the CBDT JSON only. No portal login or submission.

Live portal test:
    Requires ``--submit-live`` and an exact interactive confirmation. Portal
    credentials are loaded from the selected Client row and decrypted in
    memory. Passwords and OTP/EVC values are never printed or persisted.

Examples:
    python scripts/test_type3_real_client.py --pan <PAN>
    python scripts/test_type3_real_client.py --pan <PAN> --submit-live
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

from app.automation.auth import login_itd, logout_itd
from app.automation.browser import browser_manager
from app.automation.timing import AutomationTimeline
from app.db.database import SessionLocal
from app.db.init_db import create_tables
from app.db.models import Client, ClientITR, User
from app.eri.config import get_eri_credentials
from app.eri.type3.json_exporter import (
    Type3JsonExportError,
    export_itd_json_file,
)
from app.engine.filing_orchestrator import FilingOrchestratorError
from app.filing_automation.uploader import PortalUploadState, PortalUploader
from app.schemas.security.portal_crypto import decrypt_portal_password
from app.services.filing_record_service import upsert_filing_record


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a Type-3 CBDT JSON for one real client and optionally "
            "test foreground portal submission."
        )
    )
    parser.add_argument(
        "--pan",
        required=True,
        help="Client PAN to look up in the local Taxify database.",
    )
    parser.add_argument(
        "--assessment-year",
        default="2026-27",
        help="Assessment year (default: 2026-27).",
    )
    parser.add_argument(
        "--itr-type",
        choices=("ITR-1", "ITR-4"),
        help="Override the form saved on ClientITR. Normally auto-detected.",
    )
    parser.add_argument(
        "--submit-live",
        action="store_true",
        help=(
            "Perform a consequential portal upload/submission after generation. "
            "Requires an exact interactive confirmation."
        ),
    )
    parser.add_argument(
        "--verification-mode",
        choices=("LATER", "AADHAAR_OTP", "BANK_EVC"),
        default="LATER",
        help="Post-submission verification mode (default: LATER).",
    )
    return parser.parse_args()


def _normalize_form(value: str) -> str:
    normalized = value.strip().upper().replace("_", "-")
    if normalized in {"ITR1", "ITR4"}:
        normalized = f"ITR-{normalized[-1]}"
    if normalized not in {"ITR-1", "ITR-4"}:
        raise RuntimeError(
            f"Saved form {value!r} is not supported this season. "
            "Only ITR-1 and ITR-4 are enabled."
        )
    return normalized


def _output_dir(client_id: int, assessment_year: str) -> Path:
    return (
        ROOT
        / "downloads"
        / str(client_id)
        / assessment_year.replace("-", "_")
        / "type3-real-client-test"
    )


def _log(message: str) -> None:
    """Print operational messages emitted by privacy-filtered portal helpers."""
    print(message, flush=True)


async def _submit_live(
    *,
    client: Client,
    assessment_year: str,
    itr_type: str,
    json_path: Path,
    verification_mode: str,
) -> dict:
    """Run one foreground portal submission in a visible browser."""
    if not client.portal_password:
        raise RuntimeError(
            "The selected client has no saved ITD portal password. "
            "Save it through the Taxify client screen first."
        )
    try:
        password = decrypt_portal_password(client.portal_password)
    except Exception as exc:
        raise RuntimeError(
            "The selected client's portal password could not be decrypted. "
            "Re-save it through the Taxify client screen."
        ) from exc

    context = None
    page = None
    timeline = AutomationTimeline(_log)
    try:
        context = await browser_manager.get_context(
            log_callback=_log,
            interactive=True,
            timeline=timeline,
        )
        page = await login_itd(
            user_id=client.pan,
            password=password,
            log_callback=_log,
            context=context,
            timeline=timeline,
        )

        async def otp_callback(prompt: str) -> str:
            # getpass keeps OTP/EVC out of terminal echo and application logs.
            return getpass.getpass(f"{prompt}: ").strip()

        outcome = await PortalUploader().upload(
            page,
            assessment_year=assessment_year,
            itr_type=itr_type,
            json_path=json_path,
            verification_mode=verification_mode,
            otp_callback=otp_callback if verification_mode != "LATER" else None,
            acknowledgement_dir=json_path.parent / "acknowledgement",
            timeout_ms=300_000,
            log=_log,
        )
        return outcome.to_dict()
    finally:
        if page is not None and not page.is_closed():
            try:
                await logout_itd(page, _log, timeline=timeline)
            except Exception:
                pass
            try:
                await page.close()
            except Exception:
                pass
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
        await browser_manager.close()


def main() -> int:
    args = _parse_args()
    pan = args.pan.strip().upper()
    assessment_year = args.assessment_year.strip()

    creds = get_eri_credentials()
    if creds.mode != "type3":
        raise RuntimeError(
            f"This script requires ERI_MODE=type3; active mode is {creds.mode}."
        )

    create_tables()
    db = SessionLocal()
    try:
        clients = db.query(Client).filter(Client.pan == pan).all()
        if not clients:
            raise RuntimeError("No local Taxify client matches the supplied PAN.")
        if len(clients) > 1:
            raise RuntimeError(
                "Multiple local clients match this PAN. Resolve duplicate ownership "
                "before a real-client filing test."
            )
        client = clients[0]
        owner = db.query(User).filter(User.id == client.user_id).first()
        if owner is None:
            raise RuntimeError("The selected client's owning user was not found.")

        itr = (
            db.query(ClientITR)
            .filter(
                ClientITR.client_id == client.id,
                ClientITR.year == assessment_year,
            )
            .first()
        )
        if itr is None:
            raise RuntimeError(
                "No saved ITR draft exists for this client and assessment year."
            )
        itr_type = _normalize_form(args.itr_type or itr.itr_type)
        try:
            saved_draft = json.loads(itr.form_data)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError("The saved ITR draft is not valid JSON.") from exc
        if itr_type == "ITR-1":
            verification = (
                saved_draft.get("verification", {})
                if isinstance(saved_draft, dict)
                else {}
            )
            if not isinstance(verification, dict) or not verification.get(
                "declarationAccepted"
            ):
                raise RuntimeError(
                    "The mandatory ITR verification declaration is not accepted. "
                    "Review the return with the client, accept the declaration in "
                    "Taxify, and save the ITR before rerunning this script. "
                    "Required saved field: verification.declarationAccepted=true. "
                    "The test runner will not accept this legal declaration on the "
                    "client's behalf."
                )

        print("=" * 72)
        print("TYPE-3 REAL-CLIENT TEST")
        print(f"Client PAN:       {pan}")
        print(f"Assessment year:  {assessment_year}")
        print(f"ITR form:         {itr_type}")
        print(f"ERI environment:  {creds.environment}")
        print(f"SW_ID:            {creds.sw_id}")
        print(f"Digest iterations:{creds.digest_iterations}")
        print("=" * 72)

        json_path = export_itd_json_file(
            client_id=client.id,
            ay=assessment_year,
            itr_type=itr_type,
            flat_draft=None,
            user=owner,
            db=db,
            output_dir=_output_dir(client.id, assessment_year),
        )
        print(f"\nValidated CBDT JSON generated:\n{json_path}")

        if not args.submit_live:
            print(
                "\nSAFE MODE COMPLETE: no portal login or submission occurred.\n"
                "Manually upload this JSON as the control test, or rerun with "
                "--submit-live after confirming the artifact."
            )
            return 0

        confirmation = (
            f"SUBMIT {pan} {assessment_year} {itr_type} "
            f"{creds.environment.upper()}"
        )
        print("\nWARNING: --submit-live will perform a real portal submission.")
        print("This can create a legally consequential income-tax filing.")
        print(f"Type this exact confirmation to continue:\n{confirmation}")
        entered = input("> ").strip()
        if entered != confirmation:
            print("Confirmation did not match. Live submission cancelled.")
            return 2

        filing = upsert_filing_record(
            db=db,
            client_id=client.id,
            user_id=owner.id,
            assessment_year=assessment_year,
            itr_type=itr_type,
            eri_mode=creds.mode,
            eri_environment=creds.environment,
            status="running",
            json_path=str(json_path),
            error_message=None,
        )

        result = asyncio.run(
            _submit_live(
                client=client,
                assessment_year=assessment_year,
                itr_type=itr_type,
                json_path=json_path,
                verification_mode=args.verification_mode,
            )
        )
        state = str(result.get("state", "failed"))
        succeeded = state == PortalUploadState.SUBMITTED.value
        filing.status = (
            "verified"
            if result.get("everify_status") == "verified"
            else "submitted"
            if succeeded
            else "failed"
        )
        filing.acknowledgement_number = result.get("acknowledgement_number")
        filing.everify_status = result.get("everify_status")
        filing.acknowledgement_path = result.get("acknowledgement_path")
        filing.portal_result = json.dumps(result, ensure_ascii=False, default=str)
        filing.error_message = None if succeeded else str(result.get("reason") or "")
        db.commit()

        print("\nPortal result:")
        print(f"  state:                 {state}")
        print(f"  acknowledgement:       {result.get('acknowledgement_number') or 'not available'}")
        print(f"  e-verification status: {result.get('everify_status') or 'not available'}")
        print(f"  acknowledgement file:  {result.get('acknowledgement_path') or 'not available'}")
        if result.get("reason"):
            print(f"  reason:                {result['reason']}")
        return 0 if succeeded else 1
    except FilingOrchestratorError as exc:
        print(f"\nTEST STOPPED: {exc}", file=sys.stderr)
        if exc.errors:
            print("Blocking CBDT validation issues:", file=sys.stderr)
            for issue in exc.errors:
                print(f"  - {issue}", file=sys.stderr)
        return 1
    except (RuntimeError, Type3JsonExportError, ValueError) as exc:
        print(f"\nTEST STOPPED: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
