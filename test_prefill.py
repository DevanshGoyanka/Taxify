import asyncio
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from dotenv import load_dotenv
load_dotenv()

from app.eri.login import eri_login
from app.eri.prefill import request_prefill_otp, get_prefill_data
from app.eri.exceptions import ERIApiError

async def test_prefill():
    print("Testing Login...")
    try:
        login_resp = eri_login()
        auth_token = login_resp["authToken"]
        print(f"Login successful! Token: {auth_token[:10]}...")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    # Use a dummy PAN for now to see if we reach the ITD Gateway or get network timeout
    pan = "ABCDE1234F"
    ay = "2021" # Docs say "ERI can fetch prefill data only for current assessment year 2021"

    print("Requesting Prefill OTP...")
    try:
        req_resp = request_prefill_otp(pan, ay, "A", auth_token)
        print("OTP Request Response:", req_resp)
        tx_id = req_resp.get("transactionId")
        
        # Since this is an automated test, we won't have the real OTP from the user's phone.
        # We will attempt with a dummy OTP "111111" to see if the UAT environment accepts it or rejects it.
        print(f"Submitting dummy OTP for TxId {tx_id}...")
        prefill_data = get_prefill_data(pan, ay, auth_token, "A", tx_id, "111111")
        print("Prefill Data structure retrieved successfully!")
        
    except ERIApiError as e:
        print(f"ERI API Error: {e.code} - {e.desc}")
    except Exception as e:
        print(f"Network/Other Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_prefill())
