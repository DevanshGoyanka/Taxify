"""The JSON we hand over must be minified and must verify against itself.

The ERI Helpdesk rejected a sanity pack with two instructions: use the correct
SW_ID, and "ensure that the JSON file does not contain any unnecessary spaces,
formatting, or indentation-related whitespace, as this may impact the Sanity
Testing process" (SOP §5.6: "Remove all extra spaces in the JSON that are not
part of variable values").

Indentation is not only a style rule here. The Digest is computed over the
minified, key-sorted form; a pretty-printed file therefore does not hash to the
Digest stored inside it, so ITD's integrity check fails on bytes we generated
ourselves. These tests lock both halves down: every path that emits an ITR JSON
uses the one canonical serializer, and a written file verifies against its own
bytes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from app.eri.config import ERICredentials
from app.eri.digest import (
    compute_digest,
    digest_of_delivered_text,
    serialize_for_upload,
    verify_delivered_text,
)
from app.eri.type3.json_exporter import serialize_itd_json

ROOT = Path(__file__).resolve().parent.parent

# Deliberately fake. Real ERI secrets live only in .env, never in the repo.
FAKE_CREDS = ERICredentials(
    mode="type3",
    environment="uat",
    sw_id="SW3TEST0001",
    digest_secret_key="0123456789abcdef",
    digest_iterations=7,
)


def _document() -> dict:
    """A small ITR-shaped document with a placeholder Digest."""
    return {
        "ITR": {
            "ITR1": {
                "CreationInfo": {
                    "SWVersion": "1.0",
                    "SWCreatedBy": "SW3TEST0001",
                    "JSONCreatedBy": "SW3TEST0001",
                    "Digest": "-",
                    "IntermediaryCity": "Akola",
                },
                "Form_ITR1": {"FormName": "ITR-1", "AssessmentYear": "2026"},
                "Verification": {"Place": "Akola"},
            }
        }
    }


def _digested_document() -> dict:
    """The same document with a real Digest stamped in."""
    doc = _document()
    doc["ITR"]["ITR1"]["CreationInfo"]["Digest"] = compute_digest(doc)
    return doc


def test_serialized_output_has_no_whitespace_outside_values() -> None:
    """No newlines, no indentation, no spaces between tokens."""
    with patch("app.eri.config.get_eri_credentials", return_value=FAKE_CREDS):
        text = serialize_itd_json(_digested_document())

    assert "\n" not in text
    assert "\t" not in text
    # Strip every string literal, then assert nothing but structure remains.
    structure = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    assert " " not in structure


def test_written_file_verifies_against_its_own_bytes(tmp_path: Path) -> None:
    """The delivered bytes hash to the Digest they carry."""
    with patch("app.eri.config.get_eri_credentials", return_value=FAKE_CREDS):
        path = tmp_path / "ITR-1_minified.json"
        path.write_text(serialize_itd_json(_digested_document()), encoding="utf-8")

        assert verify_delivered_text(path.read_text(encoding="utf-8")) is True


def test_indented_file_fails_verification(tmp_path: Path) -> None:
    """The bug the helpdesk saw: indent=2 breaks the file's own Digest.

    Pretty-printing changes both the whitespace and the member order (indent
    output is insertion-ordered, the digest payload is key-sorted), so the file
    no longer hashes to the Digest inside it.
    """
    with patch("app.eri.config.get_eri_credentials", return_value=FAKE_CREDS):
        doc = _digested_document()
        path = tmp_path / "ITR-1_indented.json"
        path.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")

        assert verify_delivered_text(path.read_text(encoding="utf-8")) is False


def test_delivered_digest_matches_compute_digest() -> None:
    """The two digest entry points agree on canonical bytes.

    ``compute_digest`` hashes a dict we still hold; ``digest_of_delivered_text``
    hashes a finished file the way ITD does. On a minified file they must agree,
    or generation and verification have drifted apart.
    """
    with patch("app.eri.config.get_eri_credentials", return_value=FAKE_CREDS):
        doc = _document()
        expected = compute_digest(doc)
        text = serialize_for_upload(doc, digest=expected)

        assert digest_of_delivered_text(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        '{"ITR":{"ITR1":{"CreationInfo":{"Digest":"-"}}}}',
        '{"ITR":{"ITR1":{"CreationInfo":{"Digest":"tooshort"}}}}',
    ],
)
def test_verification_rejects_missing_or_placeholder_digest(text: str) -> None:
    with patch("app.eri.config.get_eri_credentials", return_value=FAKE_CREDS):
        assert verify_delivered_text(text) is False


# Every module that emits an ITR JSON — as an HTTP download or a file on disk.
# Kept as an explicit list so adding a new emitter is a deliberate decision.
_ITR_JSON_EMITTERS = [
    "app/routers/itr.py",
    "app/routers/client_itr.py",
    "app/routers/client_itr_v2.py",
    "app/eri/type3/json_exporter.py",
    "scripts/type3_uat_sanity.py",
]


@pytest.mark.parametrize("relative_path", _ITR_JSON_EMITTERS)
def test_no_emitter_pretty_prints_an_itr_json(relative_path: str) -> None:
    """No ITR JSON emitter may re-introduce indentation.

    These call sites each used ``json.dumps(itd_json, indent=2)`` and shipped
    files that failed the ERI sanity check. The manifest in the sanity script is
    a covering note rather than an ITR JSON, so it is allowed to stay readable.
    """
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in source.splitlines()
        if re.search(r"\bdumps?\([^)]*indent=", line)
        and "manifest" not in line
        and not line.lstrip().startswith("#")
    ]

    assert not offenders, (
        f"{relative_path} pretty-prints an ITR JSON: {offenders}. "
        "Use serialize_itd_json() — indentation breaks the Digest."
    )
