"""Unit tests for the Type-3 portal upload state machine."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.filing_automation.uploader import (
    PortalUploadOutcome,
    PortalUploadState,
    job_is_awaiting_otp,
    provide_job_otp,
    wait_for_job_otp,
)


def test_upload_outcome_serializes_expected_filing_fields() -> None:
    outcome = PortalUploadOutcome(
        state=PortalUploadState.SUBMITTED,
        acknowledgement_number="ACK123456789012",
        everify_status="pending",
    )

    assert outcome.succeeded is True
    assert outcome.to_dict() == {
        "state": "submitted",
        "acknowledgement_number": "ACK123456789012",
        "everify_status": "pending",
        "acknowledgement_path": None,
        "reason": "",
    }


def test_failed_upload_outcome_is_not_successful() -> None:
    outcome = PortalUploadOutcome(
        state=PortalUploadState.VALIDATION_FAILED,
        reason="Portal validation failed.",
    )

    assert outcome.succeeded is False
    assert outcome.to_dict()["state"] == "validation_failed"


@pytest.mark.asyncio
async def test_otp_handoff_is_memory_only_and_one_shot() -> None:
    job_id = 987654
    waiter = asyncio.create_task(wait_for_job_otp(job_id, "Enter OTP", 1))
    await asyncio.sleep(0)

    assert job_is_awaiting_otp(job_id) is True
    assert provide_job_otp(job_id, "123456") is True
    assert await waiter == "123456"
    assert job_is_awaiting_otp(job_id) is False
    assert provide_job_otp(job_id, "999999") is False


@pytest.mark.asyncio
async def test_otp_waiter_is_removed_after_timeout() -> None:
    job_id = 987655

    with pytest.raises(asyncio.TimeoutError):
        await wait_for_job_otp(job_id, "Enter OTP", 0)

    assert job_is_awaiting_otp(job_id) is False
