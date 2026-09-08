"""Tests for deterministic ERI Type-3 JSON export."""

from __future__ import annotations

import json

import pytest

from app.eri.type3.json_exporter import (
    Type3JsonExportError,
    _require_filing_digest,
    serialize_itd_json,
)


def test_serializer_is_minified_utf8_and_key_sorted() -> None:
    payload = {"z": "नमस्ते", "a": {"b": 2, "a": 1}}

    encoded = serialize_itd_json(payload)

    assert encoded == '{"a":{"a":1,"b":2},"z":"नमस्ते"}'
    assert "\n" not in encoded
    assert ": " not in encoded
    assert json.loads(encoded) == payload


def test_serializer_is_independent_of_insertion_order() -> None:
    left = {"ITR": {"ITR1": {"CreationInfo": {"Digest": "x" * 44}, "A": 1}}}
    right = {"ITR": {"ITR1": {"A": 1, "CreationInfo": {"Digest": "x" * 44}}}}

    assert serialize_itd_json(left) == serialize_itd_json(right)


def test_itr2_requires_canonical_saved_draft() -> None:
    from app.eri.type3 import json_exporter

    class Query:
        def filter(self, *args: object) -> "Query":
            return self

        def first(self) -> object:
            return type("Row", (), {"form_data": '{"form": "ITR-2"}', "itr_type": "ITR-2"})()

    class Database:
        def query(self, _: object) -> Query:
            return Query()

    with pytest.raises(Type3JsonExportError, match="canonical"):
        json_exporter.load_saved_filing_draft(
            db=Database(), client_id=1, ay="2026-27", itr_type="ITR-2"
        )


def test_export_guard_accepts_real_digest() -> None:
    payload = {"ITR": {"ITR1": {"CreationInfo": {"Digest": "x" * 44}}}}

    _require_filing_digest(payload, "ITR-1")


@pytest.mark.parametrize("digest", ["-", "", "x" * 43, "x" * 45, None])
def test_export_guard_rejects_placeholder_or_bad_digest(digest: object) -> None:
    payload = {"ITR": {"ITR4": {"CreationInfo": {"Digest": digest}}}}

    with pytest.raises(Type3JsonExportError):
        _require_filing_digest(payload, "ITR-4")
