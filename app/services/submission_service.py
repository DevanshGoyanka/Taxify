"""Submission workflow placeholder.

The production ERI submission workflow is intentionally not implemented yet.
This service remains a thin browser-automation boundary until the canonical,
idempotent return-submission pipeline replaces it.
"""

from typing import Callable, Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.automation.auth import login_itd

LogCallback = Callable[[str], None]


class SubmissionService:
    """Manage a temporary Playwright session for portal automation."""

    def __init__(self) -> None:
        """Initialize an empty browser session."""
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None

    async def init_browser(self, headless: bool = False) -> BrowserContext:
        """Initialize and return a Playwright browser context.

        Args:
            headless: Whether Chromium should run without a visible window.

        Returns:
            The initialized browser context.
        """
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        return self.context

    async def login(
        self,
        user_id: str,
        password: str,
        log_callback: Optional[LogCallback] = None,
    ) -> Page:
        """Log in to the ITD e-filing portal.

        Args:
            user_id: Portal user identifier.
            password: Portal password.
            log_callback: Optional redacted progress logger.

        Returns:
            The authenticated Playwright page.

        Raises:
            ValueError: If the browser context has not been initialized.
        """
        if self.context is None:
            raise ValueError("Browser is not initialized. Call init_browser() first.")
        logger = log_callback or print
        self.page = await login_itd(
            user_id=user_id,
            password=password,
            log_callback=logger,
            context=self.context,
        )
        return self.page

    async def submit_itr(
        self,
        itr_json: dict[str, object],
        log_callback: Optional[LogCallback] = None,
    ) -> dict[str, str]:
        """Report that production ITR submission is not implemented.

        Args:
            itr_json: Official ITD JSON artifact to submit in a future pipeline.
            log_callback: Optional redacted progress logger.

        Returns:
            A non-success status that cannot be mistaken for a submission.

        Raises:
            ValueError: If no authenticated page exists or input is empty.
        """
        if self.page is None:
            raise ValueError("Not logged in. Call login() first.")
        if not itr_json:
            raise ValueError("ITR JSON must not be empty.")
        logger = log_callback or print
        logger("[Submit] Submission is unavailable until the canonical filing pipeline is enabled.")
        return {
            "status": "not_implemented",
            "message": "ITR submission is not implemented.",
        }

    async def verify_aadhaar_otp(
        self,
        otp: str,
        log_callback: Optional[LogCallback] = None,
    ) -> dict[str, str]:
        """Report that Aadhaar OTP verification is not implemented.

        Args:
            otp: OTP supplied by the taxpayer.
            log_callback: Optional redacted progress logger.

        Returns:
            A non-success implementation status.

        Raises:
            ValueError: If the OTP is empty.
        """
        if not otp.strip():
            raise ValueError("OTP must not be empty.")
        logger = log_callback or print
        logger("[Verify] Aadhaar OTP verification is unavailable.")
        return {"status": "not_implemented", "message": "OTP verification is not implemented."}

    async def verify_evc(
        self,
        log_callback: Optional[LogCallback] = None,
    ) -> dict[str, str]:
        """Report that EVC verification is not implemented.

        Args:
            log_callback: Optional redacted progress logger.

        Returns:
            A non-success implementation status.
        """
        logger = log_callback or print
        logger("[Verify] EVC verification is unavailable.")
        return {"status": "not_implemented", "message": "EVC verification is not implemented."}

    async def close(self) -> None:
        """Close all browser resources owned by this service."""
        if self.page is not None:
            await self.page.close()
            self.page = None
        if self.context is not None:
            await self.context.close()
            self.context = None
        if self.browser is not None:
            await self.browser.close()
            self.browser = None
        if self.playwright is not None:
            await self.playwright.stop()
            self.playwright = None


submission_service: Optional[SubmissionService] = None


async def get_submission_service() -> SubmissionService:
    """Return the process-local submission service placeholder."""
    global submission_service
    if submission_service is None:
        submission_service = SubmissionService()
    return submission_service
