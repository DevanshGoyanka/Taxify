import asyncio,os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from app.automation.browser import browser_manager
from app.automation.auth import login_itd
from app.automation.downloader_26as import download_26as
from app.automation.downloader_ais_tis import run_download_ais_tis
async def run():
  L=lambda m:print(m)
  d=os.path.join(os.path.dirname(__file__),'downloads');os.makedirs(d,exist_ok=True)
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
    ok2,msg2,f2=await run_download_ais_tis(p,'2025-26',d,L)
    L(f'AIS/TIS: {ok2} - {msg2}')
  finally:
    await ctx.close();await browser_manager.close()
if __name__=='__main__':asyncio.run(run())
