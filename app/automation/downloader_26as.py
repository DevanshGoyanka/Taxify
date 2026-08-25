import os, asyncio, zipfile, shutil, re
from playwright.async_api import Page, Frame
from app.automation.downloader import update_browser_status
from app.automation.navigation import (
    PortalHandle,
    find_frame_global,
    navigate_income_tax_returns,
    race_portal_navigation,
)
from app.automation.years import TaxYearContext


async def _find_frame(page: Page, selector: str, timeout: int = 3000) -> Frame | None:
    """Return the first visible frame under one shared elapsed timeout."""
    return await find_frame_global(page, selector, timeout_ms=timeout)


async def download_26as(page: Page, assessment_year: str, download_dir: str, log_callback, pan: str = "", dob: str = "") -> tuple[bool, str, str]:
    portal_handle: PortalHandle | None = None
    try:
        tax_years = TaxYearContext.from_assessment_year(assessment_year)
        await navigate_income_tax_returns(page, timeout_ms=30000, log=log_callback)
        log_callback("[26AS] Clicking View Form 26AS — waiting for TRACES to load...")
        await update_browser_status(page, "26AS: Opening TRACES portal...")
        view_26as = page.locator("//*[contains(text(),'View Form 26AS')]").first
        await view_26as.wait_for(state="visible", timeout=30000)

        async def _trigger_traces() -> None:
            await view_26as.click()

        async def _confirm_traces() -> None:
            confirm_btn = page.locator(
                "button", has_text=re.compile(r"confirm|proceed", re.IGNORECASE)
            ).first
            try:
                await confirm_btn.wait_for(state="visible", timeout=4000)
                await confirm_btn.click()
                log_callback("[26AS] Confirmed TRACES redirect popup on ITD portal.")
            except Exception:
                return

        portal_handle = await race_portal_navigation(
            origin_page=page,
            trigger=_trigger_traces,
            portal_url=re.compile(r"(?:tdscpc|traces)", re.IGNORECASE),
            timeout_ms=40000,
            confirm=_confirm_traces,
        )
        traces_page = portal_handle.target_page
        try:
            await traces_page.wait_for_load_state("domcontentloaded", timeout=40000)
        except Exception:
            pass
        if portal_handle.child_tab:
            log_callback("[26AS] TRACES opened in a new tab.")
        else:
            log_callback("[26AS] TRACES loaded in the same tab.")

        log_callback(f"[26AS] TRACES portal ready. Frames: {len(traces_page.frames)}")
        await update_browser_status(traces_page, "TRACES: Connected.")

        # Dismiss agreement popup — TRACES loads content in frames, so search all of them
        try:
            agree_frame = await _find_frame(traces_page, "input#Details, input[type='checkbox']", timeout=20000)
            if agree_frame:
                log_callback(f"[26AS] Agreement modal found in frame: {agree_frame.url[:60]}")
                await update_browser_status(traces_page, "TRACES: Accepting Terms & Conditions...")
                chk = agree_frame.locator("input#Details").first
                await chk.click()  # click (not check) so onclick JS fires and enables the Proceed button
                await asyncio.sleep(0.3)
                proceed_btn = agree_frame.locator("input#btn").first
                await proceed_btn.wait_for(state="visible", timeout=10000)
                await proceed_btn.click()
                log_callback("[26AS] Accepted TRACES agreement popup.")
                await traces_page.wait_for_load_state("domcontentloaded", timeout=30000)
                await asyncio.sleep(1.5)
            else:
                log_callback("[26AS] No agreement popup found — continuing.")
        except Exception as err:
            log_callback(f"[26AS] Warning: Agreement popup issue ({err}). Continuing...")

        log_callback("[26AS] Navigating to Tax Credit section...")
        await update_browser_status(traces_page, "TRACES: Loading Tax Credit Section...")
        base_url = traces_page.url.rsplit('/serv/', 1)[0]
        view_url = f"{base_url}/serv/tapn/view26AS.xhtml"
        log_callback(f"[26AS] Going to: {view_url}")
        await traces_page.goto(view_url, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(1.5)

        # Handle TDS defaults intermediate page (view26ASThrdPrty.xhtml) — appears when the PAN
        # has TDS defaults from branch TANs; must click "Proceed to View Annual Tax Statement"
        if "ThrdPrty" in traces_page.url or "view26ASThrdPrty" in traces_page.url:
            log_callback("[26AS] TDS defaults page detected — clicking Proceed to View Annual Tax Statement...")
            await update_browser_status(traces_page, "TRACES: Bypassing TDS defaults page...")
            proceed = traces_page.locator("input[value*='Proceed to View']").first
            await proceed.wait_for(state="visible", timeout=20000)
            await proceed.click()
            await traces_page.wait_for_load_state("domcontentloaded", timeout=40000)
            await asyncio.sleep(1.5)
            log_callback(f"[26AS] Proceeded — now on: {traces_page.url}")

        # AY passthrough - use the assessment_year value directly as passed by caller
        log_callback(f"[26AS] Selecting Assessment Year: {assessment_year}")
        await update_browser_status(traces_page, f"TRACES: Selecting AY {assessment_year}...")
        ay_frame = await _find_frame(traces_page, "select#AssessmentYearDropDown", timeout=30000)
        if not ay_frame:
            raise Exception("Could not find AssessmentYearDropDown on TRACES view26AS page.")
        for _ay_attempt in range(3):
            try:
                # Try selecting by label first (visible text)
                await ay_frame.locator("select#AssessmentYearDropDown").first.select_option(
                    label=assessment_year, timeout=10000)
                break
            except Exception as label_error:
                try:
                    # Fallback: try selecting by value attribute
                    await ay_frame.locator("select#AssessmentYearDropDown").first.select_option(
                        value=assessment_year, timeout=10000)
                    break
                except Exception as value_error:
                    if _ay_attempt == 2:
                        raise Exception(f"Failed to select AY '{assessment_year}' by label or value. Label error: {label_error}, Value error: {value_error}")
                    log_callback(f"[26AS] AY selection failed, retrying ({_ay_attempt + 1}/3)...")
                    await asyncio.sleep(2)
        # onchange fires updatePart() which enables btnSubmit — give JS a moment
        await asyncio.sleep(1)

        log_callback("[26AS] Selecting View As: HTML")
        await update_browser_status(traces_page, "TRACES: Selecting HTML format...")
        fmt_frame = await _find_frame(traces_page, "select#viewType", timeout=20000)
        if fmt_frame:
            await fmt_frame.locator("select#viewType").first.select_option(label="HTML")
            await asyncio.sleep(0.5)

        log_callback("[26AS] Clicking View / Download...")
        await update_browser_status(traces_page, "TRACES: Fetching Form data...")
        view_btn_frame = await _find_frame(traces_page, "input#btnSubmit", timeout=20000)
        if not view_btn_frame:
            raise Exception("Could not find btnSubmit on TRACES view26AS page.")
        await view_btn_frame.locator("input#btnSubmit").first.click()

        log_callback("[26AS] Waiting for 26AS data to load...")
        await update_browser_status(traces_page, "TRACES: Loading 26AS data...")
        # The loading div is shown during AJAX fetch — wait for it to appear then disappear
        loading = traces_page.locator("#loading")
        try:
            await loading.wait_for(state="visible", timeout=8000)
            await loading.wait_for(state="hidden", timeout=60000)
        except Exception:
            await asyncio.sleep(5)  # fallback if loading div not detected

        # ── Large-file on-demand check ────────────────────────────────────────
        # TRACES shows div#message when the 26AS is too large to serve inline.
        # In that case pdfBtn/btnSubmit are absent — detect early and fail cleanly.
        for frame in traces_page.frames:
            try:
                msg_el = frame.locator("div#message")
                if await msg_el.count() > 0:
                    msg_text = (await msg_el.first.inner_text()).strip()
                    if msg_text:
                        log_callback(f"[Warning] TRACES on-demand message: {msg_text[:120]}")
                        return False, (
                            "26AS too large for inline download — login to tdscpc.gov.in "
                            "to place a download request, then download the TXT manually."
                        ), ""
            except Exception:
                continue

        # 26AS uses the current AY in TRACES and the corresponding FY in filenames.
        fy_str = tax_years.fiscal_year_filename
        prefix = f"{pan}-" if pan else ""
        os.makedirs(download_dir, exist_ok=True)

        # ── PDF download ──────────────────────────────────────────────────────
        pdf_frame = await _find_frame(traces_page, "input#pdfBtn", timeout=10000)
        if not pdf_frame:
            raise Exception("Could not find pdfBtn on TRACES view26AS page.")
        pdf_btn = pdf_frame.locator("input#pdfBtn").first

        log_callback("[26AS] Exporting Form 26AS to PDF...")
        await update_browser_status(traces_page, "TRACES: Downloading PDF file...")
        output_pdf = os.path.join(download_dir, f"{prefix}26AS-{fy_str}.pdf")
        async with traces_page.expect_download() as download_info:
            await pdf_btn.click()
        await (await download_info.value).save_as(output_pdf)
        log_callback(f"[Victory] Form 26AS PDF downloaded: {os.path.basename(output_pdf)}")

        # ── TXT download ──────────────────────────────────────────────────────
        # Switch View As to "Text" and re-submit — TRACES streams the .txt directly
        log_callback("[26AS] Switching to Text format for TXT download...")
        await update_browser_status(traces_page, "TRACES: Downloading TXT file...")
        _saved_txt = ""
        try:
            txt_fmt_frame = await _find_frame(traces_page, "select#viewType", timeout=10000)
            if txt_fmt_frame:
                await txt_fmt_frame.locator("select#viewType").first.select_option(label="Text")
                await asyncio.sleep(0.5)
            txt_btn_frame = await _find_frame(traces_page, "input#btnSubmit", timeout=10000)
            if not txt_btn_frame:
                raise Exception("btnSubmit not found for TXT download")
            output_txt = os.path.join(download_dir, f"{prefix}26AS-{fy_str}.txt")
            tmp_path = output_txt + ".download"
            async with traces_page.expect_download(timeout=30000) as txt_dl_info:
                await txt_btn_frame.locator("input#btnSubmit").first.click()
            await (await txt_dl_info.value).save_as(tmp_path)

            # TRACES wraps the .txt inside a password-protected ZIP
            # Password is DOB in ddmmyyyy format (e.g. 01-01-1980 → 11101980)
            if zipfile.is_zipfile(tmp_path):
                zip_pwd = dob.replace("-", "").encode() if dob else None
                log_callback("[26AS] Unlocking ZIP with a vault-derived password candidate.")
                with zipfile.ZipFile(tmp_path, "r") as zf:
                    names = zf.namelist()
                    txt_name = next((n for n in names if n.lower().endswith(".txt")), names[0])
                    extracted = zf.extract(txt_name, download_dir, pwd=zip_pwd)
                os.replace(extracted, output_txt)
                os.remove(tmp_path)
                log_callback(f"[Victory] Form 26AS TXT extracted from ZIP: {os.path.basename(output_txt)}")
            else:
                os.replace(tmp_path, output_txt)
                log_callback(f"[Victory] Form 26AS TXT downloaded: {os.path.basename(output_txt)}")
            _saved_txt = output_txt
        except Exception as txt_err:
            # Rename the leftover .download temp file to .zip so the user can
            # open it manually with the correct password.
            zip_hint = ""
            try:
                zip_path = output_txt.rsplit(".", 1)[0] + ".zip"
                if os.path.exists(tmp_path):
                    os.replace(tmp_path, zip_path)
                    zip_hint = f" Encrypted ZIP saved as: {os.path.basename(zip_path)}"
            except Exception:
                pass
            _txt_warning = str(txt_err)
            if "bad password" in _txt_warning.lower():
                log_callback(
                    "[Warning] TXT ZIP unlock failed — no password candidate matched. "
                    f"Verify DOB in vault matches PAN card (format: DDMMYYYY).{zip_hint}"
                )
            else:
                log_callback(f"[Warning] TXT download failed: {_txt_warning}{zip_hint}")

        await update_browser_status(traces_page, "TRACES: 26AS Download Complete!")
        await asyncio.sleep(1)
        # _saved_txt is empty if TXT extraction failed
        txt_warn = "" if _saved_txt else "PDF saved but TXT extraction failed — check DOB in vault"
        return True, txt_warn, _saved_txt
    except Exception as e:
        err = str(e)
        log_callback(f"[Error] Failed to download Form 26AS: {err}")
        # Produce a short, human-readable reason for the status column
        if "Timeout" in err or "timeout" in err:
            if "e-File" in err or "normalize-space" in err:
                reason = "Timed out — ITD dashboard still loading (try again)"
            else:
                reason = "Timed out waiting for portal response (try again)"
        elif "net::" in err.lower():
            reason = "Network error — check internet connection"
        elif "Target page" in err or "browser has been closed" in err:
            reason = "Browser closed unexpectedly"
        else:
            reason = err[:80] if len(err) <= 80 else err[:77] + "..."
        return False, reason, ""
    finally:
        if portal_handle is not None:
            try:
                await portal_handle.cleanup()
            except Exception as cleanup_error:
                log_callback(
                    f"[26AS] Warning: Could not restore ITD anchor after TRACES "
                    f"({cleanup_error})."
                )
