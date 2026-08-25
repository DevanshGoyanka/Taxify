r"""
26AS Batch Parser — Full Client Report
=======================================
Scans C:\Users\Devansh\Desktop\E-FILE_karo for:
  1. ZIP files  → extracts contained 26AS TXT files to temp_26as/
  2. TXT files  → parses with app.automation.as26_converter._parse()

For every client (PAN) it prints:
  • Personal info  (from header fields)
  • All 26AS entries across Parts I–XI
  • Summary totals per part
Then saves a JSON + pretty-print TXT report next to this script.
"""
import os, sys, json, zipfile, re, traceback, shutil
from pathlib import Path
from datetime import datetime

# -- project root --------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.automation.as26_converter import _parse, PART_META, STATUS_FULL
except ImportError as e:
    print(f"ERROR: Cannot import parser — {e}")
    sys.exit(1)

# -- paths ---------------------------------------------------------------------
E_FILE_DIR  = Path(r"C:\Users\Devansh\Desktop\E-FILE_karo")
TEMP_DIR    = E_FILE_DIR / "temp_26as"
REPORT_DIR  = PROJECT_ROOT          # report lands in the repo root

# -- helpers -------------------------------------------------------------------

def fmt_num(v):
    """Format float as Indian-comma number string."""
    if v is None or v == "" or v == "-":
        return "—"
    try:
        v = float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return str(v)
    if v < 0:
        return f"({abs(v):,.2f})"
    return f"{v:,.2f}"

def parse_amount(raw):
    """Parse a string amount to float; None if unparseable."""
    if not raw or str(raw).strip() in ("", "-"):
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        return None

def extract_pan_from_path(p: Path) -> str:
    """Pull 10-char PAN out of a path or filename."""
    m = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b', str(p))
    return m.group(1) if m else "UNKNOWN"

def extract_client_name_from_dir(p: Path) -> str:
    """Heuristic: parent folder name that does NOT look like a PAN or filename."""
    for parent in reversed(p.parents):
        name = parent.name
        # skip numeric / pure-PAN / very short names
        if re.fullmatch(r'[A-Z0-9_-]+', name) and len(name) > 20:
            continue
        if re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z].*', name):
            # strip leading PAN
            name = re.sub(r'^[A-Z]{5}[0-9]{4}[A-Z][-_]?', '', name).strip()
        if name and name not in ("E-FILE_karo", "temp_26as", "src", "Downloads"):
            return name.strip()
    return "Unknown"

def ensure_temp_dir():
    TEMP_DIR.mkdir(exist_ok=True)

# -- step 1: collect all candidate 26AS files ---------------------------------

def collect_26as_files() -> list[Path]:
    """
    Returns list of absolute Path objects for all 26AS TXT files.
    1. Scan E_FILE_DIR/temp_26as for *.txt
    2. Extract every ZIP in E_FILE_DIR that looks like a 26AS archive
    """
    ensure_temp_dir()
    collected = []

    # existing txt files
    for p in TEMP_DIR.rglob("*.txt"):
        if "26AS" in p.name.upper() or "26AS" in str(p).upper():
            collected.append(p)

    # scan top-level ZIPs
    zip_pattern = re.compile(
        r'^[A-Z]{5}[0-9]{4}[A-Z]-(\d{4}|\d{4}\s*\(\d+\))\.(zip|ZIP)$',
        re.IGNORECASE
    )
    for zp in E_FILE_DIR.glob("*"):
        if not zp.is_file():
            continue
        if not zip_pattern.match(zp.name):
            continue

        print(f"  Extracting ZIP: {zp.name}")
        try:
            with zipfile.ZipFile(zp, 'r') as zf:
                for member in zf.namelist():
                    if member.lower().endswith('.txt') and '26as' in member.lower():
                        out_path = TEMP_DIR / member
                        zf.extract(member, TEMP_DIR)
                        collected.append(out_path.resolve())
        except Exception as e:
            print(f"    [!] ZIP error: {e}")

    # deduplicate & verify
    seen, unique = set(), []
    for p in collected:
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            if p.exists() and p.stat().st_size > 100:
                unique.append(p)
            else:
                print(f"  [!] Skipping empty/locked file: {p.name}")
    return sorted(unique, key=lambda p: p.name)

# -- step 2: parse one file ----------------------------------------------------

def parse_file(txt_path: Path) -> dict:
    """Wrapper around _parse with full error handling."""
    try:
        return {"ok": True, "data": _parse(str(txt_path)), "error": None}
    except Exception as e:
        return {"ok": False, "data": None, "error": str(e),
                "traceback": traceback.format_exc()}

# -- step 3: extract personal info from header ---------------------------------

def personal_info(header: dict) -> dict:
    """Pull out the assessee's personal details from the parsed header."""
    def g(*keys, default="—"):
        for k in keys:
            v = header.get(k, "").strip()
            if v:
                return v
        return default
    return {
        "PAN"         : g("Permanent Account Number (PAN)"),
        "Name"        : g("Name of Assessee"),
        "Status"      : g("Current Status of PAN"),
        "FY"          : g("Financial Year"),
        "AY"          : g("Assessment Year", "Tax Year"),
        "Address"     : " ".join(
            g(f"Address Line {i}") for i in range(1, 6)
        ).strip() or g("Address of Assessee", default="—"),
        "State"       : g("Statecode"),
        "PIN"         : g("Pin Code"),
        "Data Updated": g("File Creation Date", "Date"),
        "Form Type"   : "Form 168" if header.get("Tax Year") else "Form 26AS",
    }

# -- step 4: summarise one part ------------------------------------------------

def summarise_part(roman: str, pdata: dict) -> dict:
    """Return a compact dict with key numbers for one part."""
    if pdata.get("empty", True):
        return {"empty": True}

    meta   = PART_META.get(roman, {})
    rows   = pdata.get("rows", [])
    result = {
        "empty"        : False,
        "title"        : meta.get("title", f"Part-{roman}"),
        "credit"       : meta.get("credit", False),
        "deductor_count": len(rows),
        "detail_count" : 0,
        "total_amount" : 0.0,
        "total_tax"    : 0.0,
        "total_deposit": 0.0,
        "entries"      : [],
    }

    for ded in rows:
        details = ded.get("_details", [])
        result["detail_count"] += len(details)

        # which amount keys to look for
        amt_key = next((k for k in (
            "Total Amount Paid / Credited(Rs.)",
            "Total Amount Paid / Debited(Rs.)",
            "Total Transaction Amount(Rs.)",
        ) if ded.get(k)), None)
        tax_key = next((k for k in (
            "Total Tax Deducted(Rs.)",
            "Total Tax Collected(Rs.)",
        ) if ded.get(k)), None)
        dep_key = next((k for k in (
            "Total TDS Deposited(Rs.)",
            "Total TCS Deposited(Rs.)",
        ) if ded.get(k)), None)

        if amt_key:
            result["total_amount"] += parse_amount(ded[amt_key]) or 0
        if tax_key:
            result["total_tax"]    += parse_amount(ded[tax_key]) or 0
        if dep_key:
            result["total_deposit"]+= parse_amount(dep_key) or 0

        # build entry row
        entry = {"deductor": "", "tan": "", "amount": None,
                 "tax": None, "deposit": None, "details": []}

        for fkey, lkey in [
            ("Name of Deductor", "deductor"),
            ("Name of Collector", "deductor"),
            ("Name of Buyer", "deductor"),
            ("Name of Seller", "deductor"),
            ("Name of Deductee", "deductor"),
            ("TAN of Deductor", "tan"),
            ("TAN of Collector", "tan"),
            ("PAN of Deductee", "tan"),
            ("PAN of Buyer", "tan"),
            ("PAN of Seller", "tan"),
            ("PAN of Deductor", "tan"),
        ]:
            if ded.get(fkey) and not entry[lkey]:
                entry[lkey] = str(ded.get(fkey) or "").strip()

        if amt_key:
            entry["amount"] = parse_amount(ded[amt_key])
        if tax_key:
            entry["tax"]    = parse_amount(ded[tax_key])
        if dep_key:
            entry["deposit"]= parse_amount(ded[dep_key])

        # individual detail rows
        for d in details:
            det = {}
            det["section"]     = d.get("Section", "").strip()
            det["txn_date"]    = d.get("Transaction Date", "").strip()
            det["status"]      = d.get("Status of Booking", "").strip()
            det["remarks"]     = d.get("Remarks", "").strip()
            for ak, tk in [
                ("Amount Paid / Credited(Rs.)", "amount"),
                ("Amount Paid / Debited(Rs.)", "amount"),
                ("Total Amount Paid / Debited(Rs.)", "amount"),
                ("Tax Deducted(Rs.)", "tax"),
                ("Tax Collected(Rs.)", "tax"),
                ("TDS Deposited(Rs.)", "deposit"),
                ("TCS Deposited(Rs.)", "deposit"),
            ]:
                val = d.get(ak, "").strip()
                if val and val != "-":
                    if det.get(tk) is None:
                        det[tk] = parse_amount(val)
            entry["details"].append(det)

        result["entries"].append(entry)

    return result

# -- step 5: full report -------------------------------------------------------

PART_ORDER = ["I","II","III","IV","V","VI","VII","VIII","IX","X_A","X_B","XI"]

def build_full_report(files: list[Path]) -> dict:
    """Parse all files and return a structured report dict."""
    report = {
        "generated_at"  : datetime.now().isoformat(),
        "total_files"   : len(files),
        "clients"       : [],
        "errors"        : [],
    }

    for fp in files:
        pan  = extract_pan_from_path(fp)
        name = extract_client_name_from_dir(fp)
        print(f"  Parsing {fp.name}  (PAN: {pan})")

        res = parse_file(fp)
        if not res["ok"]:
            err = {"file": str(fp), "pan": pan, "error": res["error"]}
            report["errors"].append(err)
            print(f"    [FAIL] Error: {res['error']}")
            continue

        data   = res["data"]
        header = data.get("header", {})
        parts  = data.get("parts", {})

        client = {
            "file_path"   : str(fp),
            "pan"         : pan,
            "client_name" : name,
            "personal"    : personal_info(header),
            "parts"       : {},
            "grand_total_credit": 0.0,
            "grand_total_tax"   : 0.0,
        }

        for roman in PART_ORDER:
            if roman in parts:
                summary = summarise_part(roman, parts[roman])
                client["parts"][roman] = summary
                if not summary.get("empty") and summary.get("credit"):
                    client["grand_total_credit"] += summary.get("total_amount", 0)
                    client["grand_total_tax"]    += summary.get("total_tax",    0)

        report["clients"].append(client)
        print(f"    [OK] {len([p for p in client['parts'].values() if not p.get('empty')])} parts, "
              f"{sum(p.get('deductor_count',0) for p in client['parts'].values())} deductors")

    return report

# -- step 6: pretty-print terminal output --------------------------------------

def print_div(text="", width=80, char="-"):
    print(f"\n{text} {char * max(0, width - len(text) - 1)}")

def print_client_report(client: dict):
    pi = client["personal"]
    print_div(">PERSONAL INFO")
    for label, key in [
        ("PAN",         "PAN"),
        ("Name",        "Name"),
        ("Status",      "Status"),
        ("Form Type",   "Form Type"),
        ("FY / AY",     "FY"),
        ("",            "AY"),
        ("Address",     "Address"),
        ("State / PIN", "State"),
        ("",            "PIN"),
        ("Data Updated","Data Updated"),
    ]:
        if key:
            v = pi.get(key, "—")
            if v and v != "—":
                print(f"  {label or key:15s}  {v}")
        else:
            v = pi.get("AY", "")
            if v:
                print(f"  {'AY':15s}  {v}")

    for roman in PART_ORDER:
        pdata = client["parts"].get(roman)
        if not pdata or pdata.get("empty"):
            continue

        meta = PART_META.get(roman, {})
        print_div(f">PART-{roman}  {meta.get('title','')}")
        print(f"  {'Deductions/Collectors':25s}  {'TAN/PAN':15s}  "
              f"{'Amount (₹)':>15s}  {'Tax (₹)':>15s}  {'Deposited (₹)':>15s}  Rows")
        print(f"  {'-'*25}  {'-'*15}  {'-'*15}  {'-'*15}  {'-'*15}  {'-'*4}")

        for entry in pdata.get("entries", []):
            ded_name = (entry["deductor"] or "—")[:25]
            tan      = (entry["tan"]      or "—")[:15]
            amt      = fmt_num(entry.get("amount"))
            tax      = fmt_num(entry.get("tax"))
            dep      = fmt_num(entry.get("deposit"))
            ndet     = len(entry.get("details", []))
            print(f"  {ded_name:25s}  {tan:15s}  {amt:>15s}  {tax:>15s}  {dep:>15s}  {ndet}")

        print(f"  {'-'*101}")
        tot_a = fmt_num(pdata.get("total_amount"))
        tot_t = fmt_num(pdata.get("total_tax"))
        tot_d = fmt_num(pdata.get("total_deposit"))
        print(f"  {'PART TOTAL':25s}  {'':15s}  {tot_a:>15s}  {tot_t:>15s}  {tot_d:>15s}")

    if client.get("grand_total_credit"):
        print_div(">GRAND TOTALS")
        print(f"  {'Total Credit Amount':30s}  {fmt_num(client['grand_total_credit']):>20s}  ₹")
        print(f"  {'Total TDS/TCS':30s}  {fmt_num(client['grand_total_tax']):>20s}  ₹")

def print_full_report(report: dict):
    print("\n")
    print("#" * 80)
    print("#   26AS BATCH PARSE REPORT")
    print("#" * 80)
    print(f"  Generated  : {report['generated_at']}")
    print(f"  Files found: {report['total_files']}")
    print(f"  Clients    : {len(report['clients'])}")
    print(f"  Errors     : {len(report['errors'])}")

    for i, client in enumerate(report["clients"], 1):
        print(f"\n\n{'='*80}")
        print(f"  CLIENT {i}/{len(report['clients'])}")
        print(f"  File: {Path(client['file_path']).name}")
        print(f"  PAN  : {client['pan']}")
        print(f"  Name : {client['personal'].get('Name','—')}  ({client['personal'].get('Form Type','—')})")
        print(f"{'='*80}")
        print_client_report(client)

    if report["errors"]:
        print_div(">ERRORS")
        for err in report["errors"]:
            print(f"  [FAIL] {Path(err['file']).name}  →  {err['error']}")

# -- step 7: save outputs ------------------------------------------------------

def save_outputs(report: dict):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = REPORT_DIR / f"26as_full_report_{ts}.json"
    txt_path  = REPORT_DIR / f"26as_full_report_{ts}.txt"

    # JSON — serialise sets/floats
    def serialise(obj):
        if isinstance(obj, float):
            return round(obj, 2)
        if isinstance(obj, dict):
            return {k: serialise(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [serialise(i) for i in obj]
        return obj

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(serialise(report), f, indent=2, ensure_ascii=False)

    # Pretty TXT
    lines = []
    def l(*args, **kw):
        sep = kw.get("sep", "  ")
        lines.append(sep.join(str(a) for a in args))

    l("=" * 80)
    l("  26AS FULL CLIENT REPORT — Taxify Batch Parser")
    l("=" * 80)
    l(f"Generated : {report['generated_at']}")
    l(f"Total files processed : {report['total_files']}")
    l(f"Clients parsed : {len(report['clients'])}")
    l(f"Errors : {len(report['errors'])}")

    for i, client in enumerate(report["clients"], 1):
        pi = client["personal"]
        l(f"\n{'-'*80}")
        l(f"CLIENT {i}  |  PAN: {pi.get('PAN','—')}  |  {pi.get('Form Type','—')}")
        l(f"  Name          : {pi.get('Name','—')}")
        l(f"  PAN Status     : {pi.get('Status','—')}")
        l(f"  FY / AY        : {pi.get('FY','—')} / {pi.get('AY','—')}")
        l(f"  Address        : {pi.get('Address','—')} {pi.get('State','—')} {pi.get('PIN','—')}".strip())
        l(f"  Data Updated   : {pi.get('Data Updated','—')}")
        l(f"  Source file    : {Path(client['file_path']).name}")

        for roman in PART_ORDER:
            pdata = client["parts"].get(roman)
            if not pdata or pdata.get("empty"):
                continue
            meta = PART_META.get(roman, {})
            l(f"\n  PART-{roman} — {meta.get('title','')}")
            l(f"  {'Deductor/Collector':30s} {'TAN/PAN':15s} {'Amount ₹':>15s} {'Tax ₹':>15s} {'Deposited ₹':>15s}")
            l(f"  {'-'*30} {'-'*15} {'-'*15} {'-'*15} {'-'*15}")
            for entry in pdata.get("entries", []):
                l(
                    f"  {(entry['deductor'] or '—')[:30]:30s}",
                    f"{(entry['tan'] or '—')[:15]:15s}",
                    f"{fmt_num(entry.get('amount')):>15s}",
                    f"{fmt_num(entry.get('tax')):>15s}",
                    f"{fmt_num(entry.get('deposit')):>15s}",
                )
                for det in entry.get("details", []):
                    st = det.get("status","")
                    l(
                        f"    - {det.get('txn_date','—')} | {det.get('section','—')} | "
                        f"Status:{st} | {fmt_num(det.get('amount'))} | {fmt_num(det.get('tax'))} | {fmt_num(det.get('deposit'))}"
                    )
            l(f"  {'-'*30+'-'*15+'-'*15+'-'*15+'-'*15}")
            l(
                f"  {'PART TOTAL':30s}",
                f"{'':15s}",
                f"{fmt_num(pdata.get('total_amount')):>15s}",
                f"{fmt_num(pdata.get('total_tax')):>15s}",
                f"{fmt_num(pdata.get('total_deposit')):>15s}",
            )

        if client.get("grand_total_credit"):
            l(f"\n  GRAND TOTAL Credit Amount : {fmt_num(client['grand_total_credit'])} ₹")
            l(f"  GRAND TOTAL TDS/TCS       : {fmt_num(client['grand_total_tax'])} ₹")

    if report["errors"]:
        l(f"\n{'-'*80}\n  ERRORS")
        for err in report["errors"]:
            l(f"  [FAIL] {Path(err['file']).name}  →  {err['error']}")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n  [FILE] JSON → {json_path}")
    print(f"  [FILE] TXT  → {txt_path}")

# -- main -----------------------------------------------------------------------

def main():
    print("#" * 80)
    print("#   26AS BATCH PARSER  —  Taxify")
    print("#" * 80)
    print(f"\n  E-FILE dir : {E_FILE_DIR}")
    print(f"  Temp dir   : {TEMP_DIR}")
    print(f"  Report dir : {REPORT_DIR}")

    print("\n--- Step 1: Collecting 26AS files ---")
    files = collect_26as_files()
    if not files:
        print("  [!] No 26AS TXT files found. Exiting.")
        return
    print(f"\n  Found {len(files)} file(s):")
    for f in files:
        print(f"    {f.name}  ({f.stat().st_size:,} bytes)")

    print("\n--- Step 2: Parsing ---")
    report = build_full_report(files)

    print("\n--- Step 3: Report ---")
    print_full_report(report)

    print("\n--- Step 4: Saving ---")
    save_outputs(report)

    print(f"\n  Done. {len(report['clients'])} clients, {len(report['errors'])} errors.")

if __name__ == "__main__":
    main()
