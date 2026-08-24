import asyncio
import os
import sys

# Make ``import app...`` work when this is run directly from tests/.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from dotenv import load_dotenv
load_dotenv()

from app.eri.login import eri_login
from app.eri.acknowledgement import get_acknowledgement
from app.eri.exceptions import ERIApiError

async def test_acknowledgement():
    print("Testing Login...")
    try:
        login_resp = eri_login()
        auth_token = login_resp["authToken"]
        print(f"Login successful! Token: {auth_token[:10]}...")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    # Replace these with real details of a return you just submitted and e-verified
    pan = "ABCDE1234F"
    ack_num = "123456789012345"

    print(f"Requesting Acknowledgement for PAN {pan}, Ack {ack_num}...")
    try:
        pdf_bytes = get_acknowledgement(pan, ack_num, auth_token)
        
        output_file = f"acknowledgement_{ack_num}.pdf"
        with open(output_file, "wb") as f:
            f.write(pdf_bytes)
            
        print(f"Successfully retrieved PDF! Saved to {output_file} ({len(pdf_bytes)} bytes)")
        
    except ERIApiError as e:
        print(f"ERI API Error: {e.code} - {e.desc}")
    except Exception as e:
        print(f"Network/Other Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_acknowledgement())
