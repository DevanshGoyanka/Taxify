import asyncio,os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from api.automation.browser import browser_manager
from api.automation.auth import login_itd
from api.automation.downloader_26as import download_26as
from api.automation.downloader_ais_tis import run_request_ais
async def run():
  L=lambda m:print(m)
  # Build AayDocCapio-compatible output path
  downloads_root = r"C:\Users\Devansh\Desktop\Taxify\downloads"
  pan = os.environ.get("ITD_PAN", "").strip()
  name = "DEVANSH SUNIT GOYANKA"  # Or derive from vault if available
  assessment_year = "2026_27"  # AY for 26AS folder naming
  out_root = os.path.join(downloads_root, f"{pan}-{name}")
  ay_folder = f"AY_{assessment_year}"
  d = os.path.join(out_root, ay_folder)
  os.makedirs(d, exist_ok=True)
  ctx=await browser_manager.get_context(log_callback=L,interactive=True)
  try:
    L('[TEST] Warming up...')
    wp=await ctx.new_page()
    await wp.goto('https://eportal.incometax.gov.in/iec/foservices/#/login',wait_until='domcontentloaded',timeout=60000)
    await asyncio.sleep(5)
    await wp.close()
    L('[TEST] Warmup done. Logging in...')
    u=os.environ.get('ITD_USER_ID','');pw=os.environ.get('ITD_PASSWORD','')
    p=await login_itd(u,pw,L,ctx)
    L('[TEST] Downloading 26AS...')
    ok,msg,f=await download_26as(p,'2026-27',d,L,pan=os.environ.get('ITD_PAN',''),dob=os.environ.get('ITD_DOB',''))
    L(f'26AS: {ok} - {msg}')
    L('[TEST] Downloading AIS/TIS...')
    result = await run_request_ais(p,'2025-26',d,L,pan=os.environ.get('ITD_PAN',''),dob=os.environ.get('ITD_DOB',''))
    ok2 = result.get('status') == 'downloaded' if isinstance(result, dict) else False
    msg2 = str(result)
    f2 = result.get('file', '') if isinstance(result, dict) else ''
    L(f'AIS/TIS: {ok2} - {msg2}')
  finally:
    await ctx.close();await browser_manager.close()
if __name__=='__main__':asyncio.run(run())
