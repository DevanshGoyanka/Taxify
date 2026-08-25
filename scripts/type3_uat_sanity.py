"""Type-3 UAT sanity pack generator (ERI Integration Plan §A11).

Produces CBDT-compliant ITR JSONs for each production-ready form (ITR-1,
ITR-4) using the active Type-3 UAT credentials (``ERI_MODE=type3``,
``ERI_ENV=uat``), runs the full CBDT Category A + schema validators, and
writes a manifest describing each generated JSON's SW_ID, Digest, and
schema status — ready to email to ``erihelp@incometax.gov.in`` for the
ITD UAT sanity check (SOP §3-4, Phase 4 of the ERI plan).

The generated JSONs carry the REAL Type-3 UAT SW_ID + a REAL 44-char
HMAC-SHA256 Digest (computed over the full document by
:mod:`app.eri.digest`), so they are the exact artefacts the ITD UAT
portal would receive. No taxpayer PII is in any fixture — these are
synthetic maximally-populated drafts.

ITR-2 and ITR-3 are not yet in the v2 canonical pipeline (Phase 6 of the
ERI plan); the manifest notes their pending status so the ITD team sees
the full scope. Once ITR-2/3 move to v2, their drafts slot in here with
no structural change.

Usage:
    python scripts/type3_uat_sanity.py
    python scripts/type3_uat_sanity.py --output-dir sanity_out
    python scripts/type3_uat_sanity.py --forms ITR-1 ITR-4
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env BEFORE any app import that reads os.environ — the Digest and
# SW_ID must flow from the active Type-3 UAT credentials.
from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

from app.eri.config import get_eri_credentials
from app.eri.digest import compute_digest
from app.engine.common.due_dates import applicable_filing_section
from app.engine.filing_gateway_v2 import FilingGatewayV2Error, generate_cbdt_json


def _apply_current_filing_section(draft: Any) -> Any:
    """Stamp the filing section that actually applies on the day of generation.

    The fixtures are pinned to 139(1), which stops being valid once the form's
    due date passes — ITR-1's went on 31 July while ITR-4 runs to 31 August, so
    a pack built in between generated ITR-4 and rejected ITR-1. The pack is
    meant to be the exact artefact the portal would receive, and a return filed
    today after the due date is belated under 139(4), so derive it rather than
    hardcode it.
    """
    section = applicable_filing_section(draft.form, draft.assessmentYear or "2026-27")
    draft.filing.filingSection = section
    return draft


def _now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 for the manifest."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _form_variants(form: str) -> list[tuple[str, Any]]:
    """Return the list of (label, ReturnDraft) variants for ``form``.

    Reuses the maximally-populated draft builders from
    :mod:`audit_itr_coverage` so the sanity pack exercises the same
    conditional branches the production audit covers.
    """
    from audit_itr_coverage import build_full_itr1_draft, build_full_itr4_draft

    if form == "ITR-1":
        # build_full_itr1_draft branches on "80EE" (see audit_itr_coverage.py:247);
        # "80EEB" matched no branch and silently produced a second copy of the
        # 80EEA draft, so the pack shipped one file twice and lost the senior-
        # citizen 80D arrays that the 80EE variant is there to exercise.
        return [
            ("default_80EEA", build_full_itr1_draft(loan_variant="80EEA")),
            ("senior_80EE", build_full_itr1_draft(loan_variant="80EE")),
        ]
    if form == "ITR-4":
        return [
            ("44AD", build_full_itr4_draft(scheme="44AD", loan_variant="80EEA")),
            ("44ADA", build_full_itr4_draft(scheme="44ADA", loan_variant="80EEA")),
            ("44AE", build_full_itr4_draft(scheme="44AE", loan_variant="80EEA")),
        ]
    raise ValueError(f"No sanity variants for {form} yet.")


def _summarize_json(form: str, official: dict) -> dict[str, Any]:
    """Extract the CreationInfo + a present-path count for the manifest."""
    form_key = form.replace("-", "")
    ci = official["ITR"][form_key]["CreationInfo"]
    return {
        "sw_created_by": ci.get("SWCreatedBy"),
        "json_created_by": ci.get("JSONCreatedBy"),
        "digest": ci.get("Digest"),
        "digest_length": len(str(ci.get("Digest", ""))),
        "json_creation_date": ci.get("JSONCreationDate"),
    }


def _digest_round_trips(form: str, official: dict) -> bool:
    """Verify the stamped Digest recomputes over the full document."""
    try:
        form_key = form.replace("-", "")
        stamped = official["ITR"][form_key]["CreationInfo"]["Digest"]
        recomputed = compute_digest(official)
        return recomputed == stamped
    except Exception:
        return False


def generate_sanity_pack(
    forms: list[str],
    output_dir: Path,
) -> dict[str, Any]:
    """Generate one JSON per ``(form, variant)`` and a manifest summary.

    Returns the manifest dict (also written to ``sanity_manifest.json``).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    creds = get_eri_credentials()
    manifest: dict[str, Any] = {
        "generated_at": _now_iso(),
        "eri_mode": creds.mode,
        "eri_environment": creds.environment,
        "sw_id": creds.sw_id,
        "digest_iterations": creds.digest_iterations,
        "forms": [],
        "notes": [
            "All JSONs are synthetic maximally-populated drafts — no taxpayer PII.",
            "Each JSON carries the real Type-3 UAT SW_ID + a real 44-char HMAC-SHA256",
            "Digest computed by app/eri/digest.py over the complete ITR document.",
            "Ready to submit to erihelp@incometax.gov.in for the ITD UAT sanity check.",
        ],
    }

    for form in forms:
        form_entry: dict[str, Any] = {"form": form, "variants": []}
        try:
            variants = _form_variants(form)
        except ValueError as exc:
            form_entry["status"] = "pending"
            form_entry["reason"] = str(exc)
            manifest["forms"].append(form_entry)
            continue

        for label, draft in variants:
            draft = _apply_current_filing_section(draft)
            variant_entry: dict[str, Any] = {
                "label": label,
                "filing_section": draft.filing.filingSection,
            }
            try:
                official, _summary = generate_cbdt_json(draft)
            except FilingGatewayV2Error as exc:
                variant_entry["status"] = "schema_failed"
                variant_entry["errors"] = list(exc.errors)[:10]
                form_entry["variants"].append(variant_entry)
                continue

            fname = f"{form}_{label}_AY{draft.assessmentYear}.json"
            fpath = output_dir / fname
            fpath.write_text(
                json.dumps(official, indent=2, default=str), encoding="utf-8"
            )
            variant_entry["status"] = "generated"
            variant_entry["file"] = fname
            variant_entry.update(_summarize_json(form, official))
            variant_entry["digest_round_trips"] = _digest_round_trips(form, official)
            form_entry["variants"].append(variant_entry)

        form_entry["status"] = (
            "generated" if all(v.get("status") == "generated" for v in form_entry["variants"])
            else "partial"
        )
        manifest["forms"].append(form_entry)

    manifest_path = output_dir / "sanity_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def main() -> int:
    """CLI entry: parse args, generate the sanity pack, print the manifest."""
    parser = argparse.ArgumentParser(
        description="Generate the Type-3 UAT sanity pack (ITR JSONs + manifest).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "downloads" / "type3_uat_sanity"),
        help="Directory to write the JSONs and manifest into.",
    )
    parser.add_argument(
        "--forms",
        nargs="+",
        default=["ITR-1", "ITR-4"],
        help="Forms to generate (default: ITR-1 ITR-4; ITR-2/3 pending v2).",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    print(f"[sanity] output dir: {output_dir}")
    print(f"[sanity] forms: {args.forms}")
    manifest = generate_sanity_pack(args.forms, output_dir)

    print(f"\n[sanity] SW_ID: {manifest['sw_id']}  ({manifest['eri_mode']}/{manifest['eri_environment']})")
    print(f"[sanity] digest iterations: {manifest['digest_iterations']}")
    for form_entry in manifest["forms"]:
        status = form_entry["status"]
        print(f"\n  {form_entry['form']}: {status}")
        if status == "pending":
            print(f"    reason: {form_entry.get('reason')}")
            continue
        for v in form_entry["variants"]:
            if v["status"] == "generated":
                print(
                    f"    [{v['label']}] {v['file']}  "
                    f"digest={v['digest'][:24]}...  "
                    f"round_trips={v['digest_round_trips']}"
                )
            else:
                print(f"    [{v['label']}] {v['status']}  errors={v.get('errors')}")
    print(f"\n[sanity] manifest: {output_dir / 'sanity_manifest.json'}")
    print(
        "[sanity] Email the JSONs + manifest to erihelp@incometax.gov.in "
        "for the ITD UAT sanity check."
    )
    # Non-zero exit if any form failed, so CI / the operator notices.
    all_ok = all(
        f["status"] in ("generated", "pending") and f["status"] != "partial"
        for f in manifest["forms"]
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
