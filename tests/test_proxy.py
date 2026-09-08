import asyncio
import os
import sys

# Make ``import app...`` work when this is run directly from tests/.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()
from app.eri.login import eri_login

async def test_nginx_proxy():
    try:
        print("Testing ERI Login via EC2 Nginx Proxy...")
        result = await eri_login()
        print(f"\nLogin Successful! Token: {result.get('authToken', '')[:10]}...")
    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_nginx_proxy())
