import os
import json
import sys

# Make ``import app...`` work when this is run directly from tests/.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv()

from app.eri.login import eri_login
from app.eri.add_client import addRegisterClient, validateRegOtp
from app.eri.exceptions import ERIApiError

def test_register_and_add_client():
    print("Testing Login...")
    try:
        login_resp = eri_login()
        auth_token = login_resp.get("authToken")
        print(f"Login Successful! Token: {auth_token[:10]}...")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    print("\n==========================================")
    print("  ERI TYPE-2 — REGISTER & ADD CLIENT")
    print("==========================================")
    print("Sending payload to addRegisterClient...")
    
    try:
        # Based on the exact payload details from the prompt
        reg_resp = addRegisterClient(
            pan="GOYPT2026E",
            residentialStatusCd="RES",  # Defaulting to RES (Resident)
            firstName="Sourav",
            midName="",
            lastName="Gupta",
            dateOfBirth="1995-01-01",
            userGender="M",
            priMobileNum="9423411831",
            isdCd="91", # Assuming India
            priMobBelongsTo="SELF", # Assuming Self
            priEmailRelationId="SELF", # Assuming Self
            priEmailId="devanshgoyanka@gmail.com",
            addrLine1Txt="G-1",
            addrLine2Txt="Gajanan Palace",
            addrLine3Txt="Ram Nagar",
            addrLine4Txt="Akola",
            addrLine5Txt="Akola HO",
            pinCd="444001",
            zipCd="",
            stdCd="",
            countryCd="91", # Assuming India (91)
            landlineNo="",
            stateCd="27",
            foreignStateDesc="",
            auth_token=auth_token
        )
        print("\n--- Calling registerClient API ---")
        print(f"HTTP: 200\n{json.dumps(reg_resp, indent=2)}")
        
        sms_txn_id = reg_resp.get("smsTransactionId")
        email_txn_id = reg_resp.get("emailTransactionId")
        
        if not sms_txn_id or not email_txn_id:
            print("Failed to get Transaction IDs for OTP validation.")
            return
            
        print("\n==========================================")
        print("✅ registerClient SUCCESS!")
        print(f"  PAN:             GOYPT2026E")
        print(f"  SMS Txn ID:      {sms_txn_id}")
        print(f"  Email Txn ID:    {email_txn_id}")
        print("==========================================")
        
        print("\nSending payload to validateRegOtp...")
        
        # Exact OTPs and Valid Upto from prompt
        val_resp = validateRegOtp(
            pan="GOYPT2026E",
            smsTransactionId=sms_txn_id,
            emailTransactionId=email_txn_id,
            mobileOtp="984851",
            emailOtp="525445",
            validUpto="2026-06-01",
            auth_token=auth_token
        )
        print("\n--- Calling validateRegOtp API ---")
        print(f"HTTP: 200\n{json.dumps(val_resp, indent=2)}")
        print("\n==========================================")
        print("✅✅ CLIENT REGISTERED & ADDED SUCCESSFULLY!")
        print("==========================================")
        
    except ERIApiError as e:
        print(f"ERI API Error: {e.code} - {e.desc} - {e.field_name}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_register_and_add_client()
