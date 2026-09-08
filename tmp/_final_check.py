"""Final confirmation using the app's own verify_delivered_text, forced to UAT."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Force the resolver to read UAT creds by setting the env it expects.
os.environ["ERI_MODE"] = "type3"
os.environ["ERI_ENV"] = "uat"
load_dotenv(Path("D:/Taxify/Taxify/.env"), override=True)
# Re-set after load in case dotenv overwrote.
os.environ["ERI_MODE"] = "type3"
os.environ["ERI_ENV"] = "uat"

import sys
sys.path.insert(0, "D:/Taxify/Taxify")
from app.eri.digest import verify_delivered_text, digest_of_delivered_text

for label, path in [
    ("ITR-1", "D:/CBDT_de30e822-69da-497e-a361-8c95f0eb1b92_2026-27 (1).json"),
    ("ITR-4", "D:/CBDT_de585d10-95bd-4e3a-9161-745dc07258da_2026-27 (1).json"),
]:
    raw = Path(path).read_text(encoding="utf-8")
    verifies = verify_delivered_text(raw)
    recomputed = digest_of_delivered_text(raw)
    import json, re
    stamped = re.search(r'"Digest"\s*:\s*"([^"]*)"', raw).group(1)
    print(f"{label}:")
    print(f"  stamped   : {stamped}")
    print(f"  recomputed: {recomputed}")
    print(f"  verifies  : {verifies}")
    print()
