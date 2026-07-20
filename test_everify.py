import asyncio
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from dotenv import load_dotenv
load_dotenv()

from app.eri.login import eri_login
from app.eri.everify import generate_evc, verify_evc
from app.eri.exceptions import ERIApiError

async def test_everify():
    print("Testing Login...")
    try:
        login_resp = eri_login()
        auth_token = login_resp["authToken"]
        print(f"Login successful! Token: {auth_token[:10]}...")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    # Replace these with real details of a return you just submitted
    pan = "ABCDE1234F"
    ack_num = "123456789012345"
    ay = "2021"
    form_code = "1"
    ver_mode = "AADHAAR"

    print(f"Generating EVC/OTP for PAN {pan}, Ack {ack_num} using mode {ver_mode}...")
    try:
        gen_resp = generate_evc(pan, ack_num, ay, form_code, ver_mode, auth_token)
        print("Generate Response:", gen_resp)
        tx_id = gen_resp.get("transactionId")
        
        # User needs to provide OTP here manually in real life
        otp = input(f"Enter the {ver_mode} OTP sent to the user: ")
        if not otp:
            print("No OTP entered, exiting.")
            return

        print(f"Verifying EVC for TxId {tx_id}...")
        verify_resp = verify_evc(pan, ack_num, ay, form_code, ver_mode, tx_id, auth_token, otp_value=otp)
        print("Verification Response:", verify_resp)
        
    except ERIApiError as e:
        print(f"ERI API Error: {e.code} - {e.desc}")
    except Exception as e:
        print(f"Network/Other Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_everify())
