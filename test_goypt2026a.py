import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from dotenv import load_dotenv
load_dotenv()

from app.eri.login import eri_login
from app.eri.prefill import request_prefill_otp
from app.eri.exceptions import ERIApiError

def test_prefill_goypt():
    print("==========================================")
    print("PREFILL TEST - GOYPT2026A")
    print("==========================================")
    
    print("Testing Login...")
    try:
        login_resp = eri_login()
        auth_token = login_resp["authToken"]
        print(f"Login successful! Token: {auth_token[:20]}...")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    pan = "GOYPT2026A"
    ay = "2025"
    otp_source = "E"

    print(f"\nRequesting Prefill OTP for PAN: {pan}, AY: {ay}, OTP Source: {otp_source}...")
    try:
        req_resp = request_prefill_otp(pan, ay, otp_source, auth_token)
        print("\n✅ SUCCESS!")
        print("Response:", req_resp)
        print(f"\nTransaction IDs:")
        print(f"  SMS Transaction ID: {req_resp.get('smsTransactionId')}")
        print(f"  Email Transaction ID: {req_resp.get('emailTransactionId')}")
    except ERIApiError as e:
        print(f"\n❌ ERI API Error: {e.code} - {e.desc}")
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")

if __name__ == "__main__":
    test_prefill_goypt()
