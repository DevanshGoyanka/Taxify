# EC2 Proxy Architecture Decision
**Date:** 2026-07-19
**EC2 IP:** 3.108.145.216
**UAT Target:** uatocpservices.incometax.gov.in (43.239.60.30)

## Current Architecture
```
Laptop (un-whitelisted IP)
  |
  | HTTPS (self-signed cert)
  v
EC2 nginx proxy (3.108.145.216) [WHITELISTED at ITD]
  |
  | HTTPS (strip /eri/ prefix)
  v
uatocpservices.incometax.gov.in:443
```

## Diagnosis Results

| Test | Result |
|------|--------|
| EC2 -> UAT HTTPS (port 443) | TIMEOUT (10s) |
| EC2 -> UAT IP (43.239.60.30) raw | TIMEOUT |
| EC2 -> UAT ping | "Time to live exceeded" - unreachable |
| EC2 -> google.com | WORKS - internet fine |
| Laptop -> UAT direct | TIMEOUT (expected, not whitelisted) |
| EC2 nginx config | CORRECT (strips /eri/, passes to UAT) |
| EC2 firewall (iptables) | ACCEPT all (no firewall) |

## Root Cause

The EC2 instance at 3.108.145.216 **cannot reach** `uatocpservices.incometax.gov.in` at all. No TCP connectivity on port 443. This is why nginx returns 504 Gateway Timeout - it proxies but the upstream is unreachable.

The UAT server at 43.239.60.30 is completely unreachable from the EC2.

## Possible Causes

1. **ITD UAT server is DOWN** - The server at 43.239.60.30 is not accepting connections from any source right now
2. **ITD changed their IP/domain** - The UAT endpoint may have changed
3. **AWS outbound routing issue** - The EC2's VPC/route-table may not route to the ITD subnet properly ("TTL exceeded" suggests a routing loop or blackhole)
4. **ITD firewall blocks AWS IP ranges** - Even though 3.108.145.216 was whitelisted, ITD may blanket-block AWS IP ranges

## Decision: Two-Pronged Approach

### Option A: Fix EC2 Proxy (investigate network)
SSH into EC2 and:
1. Install `mtr` and run `mtr 43.239.60.30` to see where packets die
2. Check if UAT DNS still resolves correctly
3. Test from a different AWS region or non-AWS VPS
4. Contact ITD to confirm UAT server status and whitelisting of EC2 IP

### Option B: Sign Locally + Direct from Laptop (if IP gets whitelisted)
- Get laptop's public IP whitelisted by ITD
- Keep `.env` pointing to `localhost:9090` for signing
- Set `ERI_BASE_URL=https://uatocpservices.incometax.gov.in/iec-uat/uat/eriapi`
- This eliminates the EC2 proxy entirely

### Recommended: Option B (simpler)

Ask ITD to whitelist the laptop's public IP. Once whitelisted:
- No EC2 proxy needed
- Sign with local DSC signer on localhost:9090
- Direct HTTPS to uatocpservices.incometax.gov.in
- Fewer failure points

## Immediate Code Changes Needed (for either option)

1. The `.env` should NOT contain the EC2 proxy URL if using direct connection
2. For Option B, set `ERI_BASE_URL=https://uatocpservices.incometax.gov.in/iec-uat/uat/eriapi`
3. The EC2 nginx config has no `/v1/` injection (confirmed correct on running instance vs deploy script)
