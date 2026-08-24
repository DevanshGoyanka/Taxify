# Taxify AWS Deployment — Running Log

Append-only. Every command run, its result, and when.
Roadmap: `Docs/AWS_FREE_TIER_DEPLOYMENT.md`

| | |
|---|---|
| **Account** | `938509046486` |
| **Identity** | `arn:aws:iam::938509046486:user/itr` (IAM user, not root) |
| **CLI profile** | `myuser` — **every command must pass `--profile myuser`** |
| **Region** | `ap-south-1` (Mumbai) |
| **Domain** | `itrbharo.duckdns.org` (confirmed by operator 2026-08-24) |

---

## Phase 0a — SUPERSEDED (old account `495199592093`)

An earlier pre-flight ran against account `495199592093` (root keys). It was **halted**: a
pre-existing `proctor-ai` stack (EC2 `t3.small` + 30 GiB gp2 + Elastic IP, us-east-1) had
already consumed 100% of the EBS allowance and ~99% of the public-IPv4 allowance, making $0
unreachable. **No resources were created there.**

Operator switched to a new account. That audit is superseded and retained only as context.

---

## Phase 0b — Pre-flight on new account `938509046486`

### 2026-08-24 — Credential discovery

```
aws configure list                     # default profile -> OLD account 495199592093
aws sts get-caller-identity --profile myuser
```
```json
{ "UserId": "AIDA5VA37SLLMFD2I4L3S",
  "Account": "938509046486",
  "Arn": "arn:aws:iam::938509046486:user/itr" }
```
Result: ✅ new account reachable under profile `myuser`. Region preconfigured `ap-south-1`.
⚠️ Default profile still points at the old account — **all commands use `--profile myuser`.**

### 2026-08-24 — First permission attempt: FAILED

```
aws ec2 describe-instances --profile myuser --region ap-south-1
```
```
UnauthorizedOperation: User arn:aws:iam::938509046486:user/itr is not authorized to
perform: ec2:DescribeInstances because no identity-based policy allows the action
```
Result: ⛔ halted. IAM user had no policies attached. Reported to operator.

### 2026-08-24 — Permissions attached by operator, re-verified

```
aws sts get-caller-identity --profile myuser --query '[Account,Arn]'
```
```
938509046486    arn:aws:iam::938509046486:user/itr
```
Result: ✅ EC2 describe calls now succeed.

### 2026-08-24 — Target region audit (ap-south-1 / Mumbai)

```
aws ec2 describe-instances      --profile myuser --region ap-south-1 --filters "Name=instance-state-name,Values=pending,running,stopping,stopped"
aws ec2 describe-addresses      --profile myuser --region ap-south-1
aws ec2 describe-key-pairs      --profile myuser --region ap-south-1
aws ec2 describe-security-groups --profile myuser --region ap-south-1
aws ec2 describe-volumes        --profile myuser --region ap-south-1
```
```
instances  : (none)
elastic ips: (none)
key pairs  : (none)
sec groups : default  sg-0496eb12236cd7128
volumes    : (none)
```
Result: ✅ Mumbai clean.

### 2026-08-24 — All-region sweep (750 hrs / IPv4 hrs are account-wide)

```
for r in $(aws ec2 describe-regions ...); do describe-instances; describe-addresses; done
```
```
(no findings in any region)
```
Result: ✅ account is completely empty. No stray instances or Elastic IPs anywhere.

### 2026-08-24 — Free tier window

```
aws iam list-roles --profile myuser --query 'sort_by(Roles, &CreateDate)[0].[RoleName,CreateDate]'
```
```
AWSServiceRoleForSupport    2026-08-24T14:14:57Z
```
Result: ✅ account created **today, 2026-08-24**. 12-month free tier runs to **~2027-08-24**.
Full allowance intact — nothing else is consuming it.

### 2026-08-24 — vCPU quota + other billable services

```
aws service-quotas get-service-quota --profile myuser --region ap-south-1 \
  --service-code ec2 --quota-code L-1216C47A
aws rds describe-db-instances / aws elbv2 describe-load-balancers / aws ec2 describe-nat-gateways
```
```
Running On-Demand Standard (A,C,D,H,I,M,R,T,Z) instances : 5.0     <- t3.micro needs 2 ✅
RDS            : (none) ✅
Load balancers : (none) ✅
NAT gateways   : (none) ✅
```
Result: ✅ quota sufficient (new accounts sometimes get 0 — this one has 5).

### Pre-flight verdict

| Check | Result |
|---|---|
| Credentials valid | ✅ |
| Correct region (Mumbai) | ✅ |
| Target region empty | ✅ |
| Account-wide empty | ✅ |
| Free tier active + untouched | ✅ (expires ~2027-08-24) |
| vCPU quota sufficient | ✅ 5 ≥ 2 |
| No ALB / NAT / RDS | ✅ |

**Cleared to proceed with §5. $0 is achievable on this account.**

---

## Phase 1 — §5 Provisioning — ✅ COMPLETE

> **Shell note:** Git Bash (MSYS) rewrites leading-slash arguments into Windows paths — it turned
> `/aws/service/...` into `C:/Program Files/Git/aws/service/...` and broke the SSM lookup.
> `MSYS_NO_PATHCONV=1` then broke the `aws` shim itself. **All AWS CLI calls use PowerShell.**
> **Every command needs `--profile myuser`** — the default profile is the old account.

### 2026-08-24 — §5.2 Default VPC + public subnet (lookup only, nothing created)

```
aws ec2 describe-vpcs    --profile myuser --region ap-south-1 --filters Name=isDefault,Values=true
aws ec2 describe-subnets --profile myuser --region ap-south-1 --filters Name=vpc-id,Values=$VPC_ID Name=default-for-az,Values=true
aws ec2 describe-internet-gateways --profile myuser --region ap-south-1
```
```
VPC_ID    = vpc-0d38055941d285070
SUBNET_ID = subnet-0decad573b3a94e85   ap-south-1c  172.31.16.0/20  MapPublicIpOnLaunch=True
IGW       = igw-06c9071ee9b7f3df0
```
Result: ✅ public subnet with IGW — no NAT Gateway needed (§3 excludes it).

### 2026-08-24 21:14 — §5.3 Key pair CREATED

Announced: EC2 key pair · §3.8 always free · 1 · needed for all §6 SSH access.
```
aws ec2 create-key-pair --profile myuser --region ap-south-1 --key-name taxify-key
```
```
taxify-key   key-0776e287e2c399152
fingerprint  97:6d:65:4e:10:e3:b9:83:d1:d7:23:4b:54:c6:63:1a:87:4a:04:f6
```
Result: ✅ created. Private key → `C:\Users\LENOVO\.ssh\taxify-key.pem`

**Follow-up:** Git Bash `chmod 400` left the file `-r--r--r--` (no real Windows ACL change);
OpenSSH refuses a world-readable key. Fixed with
`icacls ... /inheritance:r /grant:r "LENOVO:(R)"` → now `SIDDHESH-LOQ\LENOVO:(R)` only.

### 2026-08-24 — §5.4 Security group CREATED

Announced: EC2 Security Group · §3.7 always free · 1 · firewall, replaces the not-free ALB.
```
aws ec2 create-security-group --profile myuser --region ap-south-1 --group-name taxify-sg --vpc-id vpc-0d38055941d285070
aws ec2 authorize-security-group-ingress ... --port 22  --cidr 106.221.215.87/32
aws ec2 authorize-security-group-ingress ... --port 80  --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress ... --port 443 --cidr 0.0.0.0/0
```
```
SG_ID = sg-01bac042739216d64
tcp 80  80  0.0.0.0/0
tcp 22  22  106.221.215.87/32
tcp 443 443 0.0.0.0/0
port 8000 query -> (empty)
```
Result: ✅ verified. Port 8000 correctly NOT exposed — nginx proxies it on localhost.
⚠️ `106.221.215.87` is a dynamic ISP address. **SSH breaks when it rotates** — see runbook.

### 2026-08-24 — §5.5 AMI lookup (nothing created) — initially FAILED

```
aws ssm get-parameters --names /aws/service/canonical/ubuntu/server/22.04/.../ami-id
```
```
{"Parameters": [], "InvalidParameters": ["C:/Program Files/Git/aws/service/canonical/..."]}
```
Result: ⛔ **not an AWS fault** — Git Bash path mangling (see shell note above).
Retried in PowerShell:
```
AMI_ID = ami-0aa761682283b4cc8
ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20260731  x86_64  ebs  2026-07-31
```
Result: ✅ resolved.

### 2026-08-24 — §5.6 EC2 instance + EBS volume CREATED

Announced: t3.micro · §3.1 750 hrs/mo · 744 hrs · only compute.
Announced: 16 GiB gp3 · §3.2 30 GB limit · 16 GB · OS + venv + Chrome + 2 GB swap.
```
aws ec2 run-instances --profile myuser --region ap-south-1 \
  --image-id ami-0aa761682283b4cc8 --instance-type t3.micro --key-name taxify-key \
  --credit-specification CpuCredits=standard \
  --security-group-ids sg-01bac042739216d64 --subnet-id subnet-0decad573b3a94e85 \
  --associate-public-ip-address --block-device-mappings file://bdm.json \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=taxify}]'
```
```
INSTANCE_ID = i-06fa754bdb98c95af
state       = running
```

### 2026-08-24 — §5.6b Credit-mode verification (the §4.9 guard)

```
aws ec2 describe-instance-credit-specifications --profile myuser --region ap-south-1 --instance-ids i-06fa754bdb98c95af
```
```
standard                                          <-- REQUIRED. Not "unlimited".
t3.micro  running  15.207.237.158  172.31.27.231  ap-south-1c
vol-0ed5c1f4e9dd78914   16   gp3   3000 IOPS   in-use
account-wide instance count: i-06fa754bdb98c95af  (exactly 1, §4.3 ✅)
```
Result: ✅ **`standard` confirmed** — surplus CPU credits can never be billed.

### 2026-08-24 — §5.7 Elastic IP CREATED + associated

Announced: Elastic IP · §3.3 750 hrs/mo public IPv4 (12 mo only) · 744 hrs · stable DNS target.
```
aws ec2 allocate-address  --profile myuser --region ap-south-1 --domain vpc
aws ec2 associate-address --profile myuser --region ap-south-1 --instance-id i-06fa754bdb98c95af --allocation-id eipalloc-03d23487a47ffde51
```
```
ALLOC_ID      = eipalloc-03d23487a47ffde51
ASSOCIATION   = eipassoc-03768b8c3b44ba343
PUBLIC IP     = 43.205.225.117
account-wide public IPv4 count: 1
```
Result: ✅ **attached** (§4.2 — an unattached EIP bills immediately; this one is not).
Associating replaced the auto-assigned `15.207.237.158`, so still only ONE public IPv4.

### 2026-08-24 — §5.8 Budget CREATED — first attempt FAILED

```
aws budgets create-budget --account-id 938509046486 ...        # no --profile
```
```
AccessDeniedException: AccountId : 938509046486 does not match the credentials provided
```
Result: ⛔ operator error — `--profile myuser` omitted, so it authenticated as the OLD account.
Retried with the flag:
```
aws budgets create-budget --profile myuser --account-id 938509046486 ...
taxify-zero   1.0   MONTHLY
ACTUAL  GREATER_THAN  1.0
```
Result: ✅ created. Alert email: `sidworkcode18@gmail.com`.

### 2026-08-24 — §5 end-to-end verification: SSH

```
ssh -i ~/.ssh/taxify-key.pem ubuntu@43.205.225.117 "hostname; lsb_release -ds; nproc; free -m; df -h /"
```
```
CONNECTED
ip-172-31-27-231
Ubuntu 22.04.5 LTS
2                       <- vCPU
Mem: 914 MB total       <- confirms §2.3: swap is MANDATORY
/dev/root  16G  1.8G  14G  12% /
```
Result: ✅ key pair + SG rule + EIP + instance all work together.

### 2026-08-24 — §5.9 DuckDNS re-pointed at the Elastic IP

Not an AWS resource — free third-party DNS, used because Route 53 is not free (§3) and
Let's Encrypt will not issue a certificate for a bare IP.

```
GET https://www.duckdns.org/update?domains=itrbharo&token=<REDACTED>&ip=43.205.225.117
```
```
response: OK
```

Verification:
```
Resolve-DnsName itrbharo.duckdns.org      -> 43.205.225.117
Resolve-DnsName www.itrbharo.duckdns.org  -> 43.205.225.117   (wildcard works)
Resolve-DnsName itrbharo.duckdns.org -Server 1.1.1.1 -> 43.205.225.117  (independent resolver)
```
Result: ✅ live and propagated. Both apex and `www` resolve, so §6.10 can issue a certificate
covering both names.

> **Secret handling:** the DuckDNS token is deliberately redacted here. It is not stored on the
> box and not committed anywhere. Because the deployment uses a **static Elastic IP**, no
> DuckDNS updater daemon is needed — the record never has to change.

### §5 verdict

| Check | Result |
|---|---|
| All 6 resources created | ✅ |
| Every resource inside §3 ledger | ✅ |
| `CpuCredits=standard` (§4.9) | ✅ |
| EIP attached, not idle (§4.2) | ✅ |
| Exactly 1 instance account-wide (§4.3) | ✅ |
| Exactly 1 public IPv4 (§3.3) | ✅ |
| Port 8000 not exposed | ✅ |
| SSH reachable | ✅ |
| **Projected monthly cost** | **$0.00** |

**§5 COMPLETE — halted for operator confirmation before §6.**

---

## Phase 2 — §6 Box setup — ✅ COMPLETE (service starts in §7)

> **Method note:** inline heredocs through PowerShell→ssh proved fragile — a `§` character and
> later `\$` escaping both corrupted the remote quoting. **All remote work is done by writing a
> script locally with LF endings, `scp`-ing it, and executing it.** Reproducible and auditable.

### 2026-08-24 — Repo branch trap caught before deploying

```
git ls-remote --symref https://github.com/DevanshGoyanka/Taxify HEAD
```
```
ref: refs/heads/master   HEAD          <-- default branch is master
refs/heads/main    86ff96b             <-- the real app + guard fix
refs/heads/master  7bea0ce             <-- stale "push automation" line of work
```
Result: ⚠️ roadmap §6.4's plain `git clone` would have silently deployed **master**.
**All clones use `-b main`.**

### 2026-08-24 — §6.1/6.2 Base packages + Node 20

First attempt failed: a `§` character in the inline script corrupted bash quoting
(`syntax error near unexpected token '('`). Re-run via scp'd script file.
```
python3.10 --version -> Python 3.10.12
git                  -> 2.34.1
nginx                -> 1.18.0 (Ubuntu)
node / npm           -> v20.20.2 / 10.8.2
sqlite3              -> 3.37.2
```
Result: ✅ Python 3.10 matches the operator's working interpreter.

### 2026-08-24 — §6.3 Swap (mandatory)

```
sudo fallocate -l 2G /swapfile; mkswap; swapon; + /etc/fstab entry
```
```
Mem:   914Mi total
Swap:  2.0Gi total, 0B used
```
Result: ✅ persistent across reboot via fstab.

### 2026-08-24 — §6.4/6.5 Code + venv

```
git clone -b main https://github.com/DevanshGoyanka/Taxify /opt/taxify
python3.10 -m venv .venv && pip install -r requirements.txt
pip install email-validator httpx urllib3 pytest-asyncio   # under-declared in requirements.txt
```
```
branch: main   head: 86ff96b
guard check: 'OK: stale guard absent'
import check: all core imports OK (fastapi, uvicorn, playwright, fitz, pikepdf,
              email_validator, httpx, jsonschema, sqlalchemy)
```
Result: ✅ the §2.1 guard removal is live on the box.

### 2026-08-24 — §6.6 Playwright + Chrome (Chrome only, not Chromium)

```
sudo ./.venv/bin/playwright install --with-deps chrome
```
```
/usr/bin/google-chrome
Google Chrome 151.0.7922.173
/opt/taxify/.playwright -> 5.0M   (ffmpeg only; bundled Chromium correctly skipped)
disk: 6.4G used / 16G  (42%)
```
Result: ✅ ~450 MB saved by not installing the unused bundled Chromium.

### 2026-08-24 — §6.7 Frontend build — FAILED, then fixed

```
npm run build   ->  tsc -b failed
```
```
14 errors, all TS2322, all in src/components/business/ITR4ScheduleBPManager.tsx (lines 228-229)
Type 'string | number | undefined' is not assignable to type 'number | undefined'
```
Root cause: `derive()` typed the coerced record as `number | string | undefined` while `sum()`
takes `Array<number | undefined>`. Runtime was already correct (toNum coerces everything);
only the annotation was wrong. Pre-existing, introduced with c98d763 / 2857b46.

Operator chose **Option 1 — fix the type**. Commit `c6e6ac5`: build the coerced values into a
separate `Record<string, number | undefined>` instead of overwriting in place.

Re-run after pull:
```
TSC PASSED
dist/assets/index-BYIpKCAg.js   989.59 kB | gzip: 247.68 kB
built in 4.71s, dist/ = 1.1M
API URL baked into dist/assets/axiosInstance-C6dy_tRd.js  ✅
```
Result: ✅ built with `VITE_API_BASE_URL=https://itrbharo.duckdns.org`.

### 2026-08-24 — §6.13 SQLite WAL (commit `9ac67f7`)

Verified locally before pushing:
```
PRAGMA journal_mode -> wal ; busy_timeout -> 5000 ; synchronous -> 1 (NORMAL)
```
Result: ✅ prevents `database is locked` between the automation worker and the API.

### 2026-08-24 — §6.8 systemd unit

```
/etc/systemd/system/taxify.service  (installed, enabled)
/etc/taxify/taxify.env              (created, 600, root:root, EMPTY until section 7)
/opt/taxify/.env -> symlink to the above
```
Unit carries the 1 GB survival tuning: `MemoryMax=750M`, `MemoryHigh=650M`,
`KillMode=control-group`, `OOMPolicy=continue`, `--workers 1` (browser.py singleton),
and `xvfb-run` for the visible-Chrome path (§2.2).
Result: ✅ enabled. **Deliberately not started** — no secrets yet.

### 2026-08-24 — §6.9 nginx

```
nginx: configuration file /etc/nginx/nginx.conf test is successful
http://127.0.0.1/           -> 200
http://itrbharo.duckdns.org/ -> 200
```
Result: ✅ frontend serving. Default site unlinked. gzip + immutable asset caching applied.

### 2026-08-24 — §6.11 cron

```
0 3 * * *    find /opt/taxify/downloads -type f -mtime +30 -delete
*/30 * * * * pkill -f "chrome.*--headless" --older-than 7200 || true
```
Result: ✅ EBS creep guard (§4.5) + leaked-Chrome reaper.

### 2026-08-24 — §6.10 Let's Encrypt TLS

```
sudo certbot --nginx -d itrbharo.duckdns.org -d www.itrbharo.duckdns.org --redirect
```
```
Certificate Name: itrbharo.duckdns.org
Domains:          itrbharo.duckdns.org www.itrbharo.duckdns.org
Expiry:           2026-11-22 (89 days)
certbot.timer:    active, next run in 14h
certbot renew --dry-run: all simulated renewals succeeded
```
Result: ✅ HTTPS live, auto-renew proven by dry-run.

### 2026-08-24 — §6 external verification (from operator machine)

```
https://itrbharo.duckdns.org/       status=200  ssl_verify_result=0
https://www.itrbharo.duckdns.org/   status=200
http://itrbharo.duckdns.org/        301 -> https://itrbharo.duckdns.org/ -> 200
/assets/*.js                        Content-Encoding: gzip
                                    Cache-Control: public, immutable, max-age=31536000
POST /auth/login                    502   <- EXPECTED, app not started until section 7
TLS subject CN=itrbharo.duckdns.org  issuer CN=YR1, O=Let's Encrypt  expires 2026-11-22
```

### §6 verdict

| Check | Result |
|---|---|
| Packages + Node installed | ✅ |
| 2 GB swap, persistent | ✅ |
| Correct branch (`main`) deployed | ✅ |
| venv + all imports | ✅ |
| Chrome installed, Chromium skipped | ✅ |
| Frontend built (after type fix) | ✅ |
| systemd unit enabled w/ memory caps | ✅ (not started) |
| nginx serving over HTTPS | ✅ |
| HTTP→HTTPS redirect | ✅ 301 |
| gzip + immutable caching | ✅ |
| TLS auto-renew | ✅ dry-run passed |
| **AWS resources added in §6** | **none — $0 unchanged** |

**§6 COMPLETE — halted for operator confirmation before §7 (env/secrets).**

---

## Phase 3 — §7 Env vars and secrets — ✅ COMPLETE

Operator decisions: transfer the local `.env` (option B), copy `app.db` to keep users, reuse
`SECRET_KEY`/`PORTAL_ENCRYPTION_KEY` unrotated, run **Type-3 UAT**.

### 2026-08-24 — ERI mode decision

Investigated which `(ERI_MODE, ERI_ENV)` pair is actually usable:
```
local .env: ERI_MODE=type3  ERI_ENV=uat  ERI_DSC_SIGNING_MODE=token  ERI_INTERMEDIARY_CITY=Akola

ERI_SW_ID_TYPE3_PRODUCTION            = (EMPTY)
ERI_DIGEST_SECRET_KEY_TYPE3_PRODUCTION= (EMPTY)
ERI_USER_ID_TYPE3_PRODUCTION          = (EMPTY)
```
`.env` labels that block *"Type-3 Production (to be filled before the filing season)"* — it was
never populated. `ERI_ENV=production` would raise `ValueError` at `config.py:151` (missing
SW_ID) before the app finished booting.

**Decision: deploy Type-3 UAT. Production keys left EMPTY, to be filled when ITD issues them.**
Flipping later is `ERI_ENV=production` + three values + `systemctl restart taxify`.

### 2026-08-24 — Env file prepared locally

CRLF stripped (systemd `EnvironmentFile` would otherwise embed a trailing `\r` in every value).
URLs pointed at the deployed domain:
```
FRONTEND_URL=https://itrbharo.duckdns.org
CORS_ALLOWED_ORIGINS=https://itrbharo.duckdns.org,https://www.itrbharo.duckdns.org
39 keys total, 0 CR characters
```

### 2026-08-24 — app.db copy — first attempt FAILED

```
sqlite3 PRAGMA wal_checkpoint(TRUNCATE) / journal_mode=DELETE
-> sqlite3.OperationalError: database is locked
```
Cause: the operator's local dev server (PID 23924, port 8000) still holds `app.db` open.
Resolved with SQLite's **online backup API** (`Connection.backup()`), which snapshots a live
database without an exclusive lock:
```
users in copy : 3
    id=1  csiddhesh3011@gmail.com
    id=3  siddhesh@yugansh.com
    id=2  test@example.com
integrity     : ok
tables        : 9
size          : 917504 bytes
```

### 2026-08-24 — Install on box

```
sudo install -m 600 -o root -g root /tmp/taxify.env /etc/taxify/taxify.env
install -m 644 -o ubuntu -g ubuntu  /tmp/app.db     /opt/taxify/app.db
```
```
keys: 39
ERI_MODE=type3 / ERI_ENV=uat / city=Akola / DSC=token
production TYPE3 keys: all empty (deliberate)
users on box: 3
```

### 2026-08-24 — Service start FAILED, then fixed

```
PermissionError: [Errno 13] Permission denied: '/opt/taxify/.env'
  at app/main.py:19 -> load_dotenv()
```
Root cause: **two** independent readers of the environment.
1. systemd reads `EnvironmentFile=` as **root**, then drops to `User=ubuntu` — worked.
2. `app/main.py:19` *also* calls `load_dotenv()`, opening the `/opt/taxify/.env` symlink as
   **ubuntu** — blocked by `600 root:root`.

Operator chose **Option 1** — standard service-credential ownership:
```
sudo chown root:ubuntu /etc/taxify/taxify.env
sudo chmod 640        /etc/taxify/taxify.env
```

### 2026-08-24 — Secrets permission audit

```
/etc/taxify/taxify.env   mode=640  root:ubuntu    other users: BLOCKED
/opt/taxify/.env.backup  mode=640  ubuntu:ubuntu  other users: BLOCKED
/opt/taxify             mode=755  ubuntu:ubuntu
```
Note: `app/security/env_backup.py` writes `.env.backup` on every start — it creates the file
with safe `640` permissions of its own accord. Verified with an actual `sudo -u nobody cat`
rather than trusting the mode bits.

### 2026-08-24 — Service running

```
Active: active (running)   Main PID 16796 (xvfb-run)
Memory: 129.2M (high: 650.0M  max: 750.0M  available: 520.7M)
INFO: .env backed up to /opt/taxify/.env.backup
[OK] Database tables created and additive migrations applied.
INFO: Background worker task created / Job worker loop started.
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000
GET 127.0.0.1:8000/docs -> 200
```

### 2026-08-24 — End-to-end chain verification (public HTTPS)

```
POST /auth/login  wrong password on real user  -> 401  (app reached SQLite, rejected creds)
POST /auth/login  malformed body               -> 422  (FastAPI validation alive)
GET  /                                         -> 200  (static frontend)
OPTIONS /auth/login  Origin: itrbharo...       -> 200
    access-control-allow-origin: https://itrbharo.duckdns.org
    access-control-allow-credentials: true
```
Result: ✅ HTTPS → nginx → uvicorn → SQLite proven end to end.

### §7 verdict

| Check | Result |
|---|---|
| 39 keys installed, LF endings | ✅ |
| Mode = Type-3 UAT, production keys empty | ✅ |
| `app.db` copied, 3 users, integrity ok | ✅ |
| Secrets not world-readable (verified by test, not assumption) | ✅ |
| Service active, worker running | ✅ |
| Memory 129 M against a 750 M cap | ✅ |
| CORS allows the deployed origin | ✅ |
| **AWS resources added in §7** | **none — $0 unchanged** |

**§7 COMPLETE — halted for operator confirmation before §8.**

---

## Phase 4 — §8 Verification — ✅ COMPLETE (3 issues found, 2 fixed)

### 2026-08-24 — §8.1/8.2/8.5/8.6/8.7 pre-reboot

```
taxify: active   nginx: active   (both enabled at boot)
127.0.0.1:8000/docs -> 200
Mem 258Mi/914Mi   Swap 54Mi used of 2.0Gi
cgroup MemoryCurrent=142MB  MemoryMax=750MB
disk 6.7G/16G (44%)

Playwright: chrome 151.0.7922.173 launched, page rendered -> OK
ERI:  type3/uat  sw_id=SW20014122  digest secret set  iterations=1038
      assert_credentials_at_startup(): PASS
```

### 2026-08-24 — §8.4 REBOOT SURVIVAL TEST

```
sudo systemctl reboot        # SSH back after ~45s
booted at 2026-08-24 16:46:23 (fresh boot confirmed)

taxify: active      <- no manual start
nginx : active      <- no manual start
swap  : /swapfile 2G re-mounted from fstab
API   : 127.0.0.1:8000/docs -> 200
SQLite: journal_mode=wal preserved
certbot.timer: active
crontab: both jobs survived
Elastic IP 43.205.225.117 still attached to i-06fa754bdb98c95af
CpuCredits still 'standard'
```
Result: ✅ full unattended recovery.

### 2026-08-24 — §8.3 verified by REAL operator usage

nginx access log showed live traffic from `106.221.215.87`: registration
(`siddheshchaudhari52@gmail.com`, user id 4), `POST /auth/login -> 200`, client browsing,
and an import job triggered. Better evidence than a synthetic check.

### ISSUE 1 — nginx routed most API calls to index.html (introduced by this deployment)

The roadmap's location regex `^/(auth|clients|eri|filing|automation|integration|health)` was
guesswork. Authoritative list from the running app's `/openapi.json` — **18 top-level segments**:
```
api auth automation business-income capital-gains clients dashboard health
integration itr1 itr2 itr3 itr4 me pan returns tax-summary v2
```
* 13 segments were NOT proxied -> returned `index.html` (542 bytes) instead of JSON.
  Observed live: `/v2/clients/... -> 200 542` and `/dashboard/stats -> 200 542`.
* `eri` was in the regex but is not an API segment at all.
* `filing` IS an SPA route -> the operator's deep link `/filing/<id>/2026-27` returned **404**.

Complication: `/clients` and `/dashboard` are **both** SPA routes and API routes, so path
matching cannot separate them.

**Fix:** dispatch on the `Accept` header — browser navigations (`text/html`) get `index.html`,
everything else proxies to uvicorn.
```nginx
location / { try_files $uri @dispatch; }
location @dispatch {
    if ($http_accept ~* "text/html") { rewrite ^ /index.html last; }
    proxy_pass http://127.0.0.1:8000;
}
```
TLS re-applied afterwards with `certbot install --cert-name ... --nginx --redirect`
(replacing the site file discards certbot's server block).

Verification — API side, no 542-byte responses remain:
```
/health                      -> 200 15    (real JSON)
/dashboard/stats             -> 401 62    (was 200 542)
/clients?assessmentYear=...  -> 401 62
/me /returns /automation/... -> 401 62
/v2/clients /pan /itr1 ...   -> 404 22    (API's own 404, not HTML)
```
Verification — SPA side, all 200 542 (index.html):
```
/  /login  /register  /dashboard  /clients  /filing
/filing/af19a74f-.../2026-27   -> 200      (was 404)
/advanced-tax  /some-unknown-deep-link
```

### ISSUE 2 — automation jobs failed on a root-owned home dir (introduced by this deployment)

```
job 36 | failed | DOWNLOAD_ALL
PermissionError: [Errno 13] Permission denied: '/home/ubuntu/.local/share/AayDocCapio'
  browser.py:61 -> os.makedirs(path)
```
```
/home/ubuntu              ubuntu:ubuntu
/home/ubuntu/.local       root:root   <- created 16:09
/home/ubuntu/.local/share root:root
```
Cause: `sudo -E ./.venv/bin/playwright install` in §6.6 preserved `HOME=/home/ubuntu` while
running as root, so Playwright created those directories owned by root.

**Fix:** `sudo chown -R ubuntu:ubuntu /home/ubuntu/.local`

Verified through the app's own code path (not a synthetic test):
```
_playwright_browsers_dir() -> /home/ubuntu/.local/share/AayDocCapio/browsers   (no error)
browser_manager.get_context() -> page rendered "worker-path-ok"
```

> Related finding: `browser.py:150` **overwrites** `PLAYWRIGHT_BROWSERS_PATH` with its own
> `~/.local/share/AayDocCapio` path, so the systemd `Environment=` setting is silently ignored
> and roadmap §4.5's "pin the browsers path" guard does not actually work. Harmless here —
> `channel="chrome"` uses system Chrome at `/usr/bin/google-chrome` — but the roadmap claim
> is wrong.

### ISSUE 3 — job 35 failure is operator data, not infrastructure

```
35 | failed | DOWNLOAD_ALL | Client is missing PAN or ITD portal password.
```
Expected behaviour. That client has no `portal_password` set. Not a deployment defect.

### 2026-08-24 — §8.8 Free tier position

```
instances account-wide : i-06fa754bdb98c95af  t3.micro  running   (exactly 1)
CpuCredits             : standard
EBS volumes            : vol-0ed5c1f4e9dd78914  16 GiB gp3        (of 30 GB)
public IPv4            : 1                                        (of 750 hrs/mo)
snapshots              : none
budget                 : taxify-zero  $1
all-region stray sweep : clean
```

### §8 verdict

| # | Check | Result |
|---|---|---|
| 8.1 | taxify + nginx active | ✅ |
| 8.2 | local API 200 | ✅ |
| 8.3 | app loads, login works | ✅ (real operator usage) |
| 8.4 | survives reboot unattended | ✅ |
| 8.5 | swap in use, memory healthy | ✅ |
| 8.6 | Playwright/Chrome launches | ✅ (after Issue 2 fix) |
| 8.7 | ERI credentials resolve (Type-3 **UAT**) | ✅ |
| 8.8 | free tier all within limits | ✅ |
| — | API routes return JSON | ✅ (after Issue 1 fix) |
| — | SPA deep links return HTML | ✅ (after Issue 1 fix) |
| — | **Monthly cost** | **$0.00** |

**§1–9 COMPLETE AND VERIFIED.** `docs/runbook.md` written.

---

## Phase 5 — post-verification incidents

### 2026-08-24 — SSH lost to CGNAT; replaced with SSM

`ssh: connect to host 43.205.225.117 port 22: Connection timed out`

Diagnosis — the operator's public IP had rotated again, and sampling revealed **Carrier-Grade
NAT**: four probes one second apart returned **two different addresses**.
```
sample 1 : checkip=42.104.221.14   ipify=42.104.220.7     <- two IPs, same second
sample 2 : checkip=42.104.220.7    ipify=42.104.220.7
```
Same-day history: `106.192.216.31` -> `106.221.215.87` -> `42.104.220.7`.
Re-authorising the observed `/32` did **not** restore access, because the SSH connection left
through a different pool address. A `/32` rule is structurally unworkable under CGNAT.

> The Elastic IP `43.205.225.117` never changed. It is the **server's** address; the firewall
> rule filters on the **client's**. The site stayed up for everyone throughout.

**Fix (operator chose SSM):** created IAM role + instance profile `taxify-ssm`, attached to the
running instance with no reboot. Agent registered `Online` (v3.3.4793.0) after ~3 min.
**Port 22 ingress then revoked entirely.** Verified command execution still works with 22 closed.

### 2026-08-24 — portal automation: `No module named 'pdfplumber'`

```
job 39 | completed (with errors)
  26AS extraction failed: No module named 'pdfplumber'
  AIS  extraction failed: ModuleNotFoundError: No module named 'pdfplumber'
  TIS  extraction failed: ModuleNotFoundError: No module named 'pdfplumber'
```

Rather than fix one import and hit the next, an AST walk over `app/` and `ais_extractor/`
audited every third-party import against the installed set. **Nine** were undeclared:
`pdfplumber`, `requests`, `xlsxwriter`, `openpyxl`, `reportlab`, `httpx`, `email-validator`,
`pytest-asyncio`, `urllib3`.

All are **lazy imports inside functions**, so the app starts cleanly and only fails when a user
exercises the feature — which is why a fresh install looked healthy.

Fixed in `a856e48`; verified on the box:
```
pdfplumber 0.11.10 ; ais_pdfplumber / tis_pdfplumber / as26_extractor all import
```
`win32crypt` is correctly absent — Windows-only DSC signing, guarded by try/except.

Also noted: job 38 failed with `Invalid Password` (client's stored ITD portal password),
job 35 with `missing PAN or portal password`. Both are operator data, not infrastructure.

### 2026-08-24 — nginx Accept-dispatch was too broad

The §8 fix made *all* routing depend on the `Accept` header, so any non-browser client
(`curl`, health checks, monitoring) got proxied to the API and 404'd on `/` and `/login`.
Browsers were unaffected.

Replaced with a deterministic config driven by the app's own `/openapi.json`:
* exact SPA locations for `/`, `/login`, `/register`, `/dashboard`, `/advanced-tax`, `/filing`
* explicit API prefixes for the 16 non-colliding segments, plus `/clients/` and `/dashboard/`
* Accept-dispatch retained for **`/clients` only** — the single genuine collision, being both
  an SPA page and a `GET`/`POST` API route

Verified in all three modes: plain curl SPA routes 200, browser navigation 200, API routes
return real API responses with no 542-byte `index.html` leaking through.

---

## Phase 6 — §10 CI/CD

### 2026-08-24 — AWS side

```
aws iam create-open-id-connect-provider  token.actions.githubusercontent.com
aws iam create-role                      taxify-gha-deploy
aws iam put-role-policy                  taxify-ssm-deploy  (inline, least privilege)
```
The inline policy permits only `ssm:SendCommand` against
`instance/i-06fa754bdb98c95af` + the `AWS-RunShellScript` document, plus read-only
`GetCommandInvocation`. No long-lived AWS keys exist in the repository.

### 2026-08-24 — `/opt/taxify/deploy.sh`

Pull, conditional `pip install` (only when `requirements.txt` changed), atomic frontend swap
from a GitHub Release asset, restart, health check, and rollback of the previous bundle if the
service fails to start. Dry run:
```
=== deploy start 2026-08-24T17:46:45+00:00 ===
code: a856e48 -> a856e48
requirements.txt unchanged - skipping pip
health: /docs -> 200
=== deploy OK: a856e48 ===
```

### 2026-08-24 — first pipeline run FAILED at OIDC

Run `32758799410` on `fe7239f`:
```
changes         success
build-frontend  success   (Release asset published)
deploy          FAILURE   at aws-actions/configure-aws-credentials@v4
```
GitHub's job log needs auth, so the cause came from CloudTrail:
```
errorCode    : AccessDenied
errorMessage : Not authorized to perform sts:AssumeRoleWithWebIdentity
sub actually sent:
  repo:DevanshGoyanka@102995309/Taxify@1303961107:ref:refs/heads/main
sub my trust policy expected:
  repo:DevanshGoyanka/Taxify:ref:refs/heads/main
```
GitHub issues the **immutable subject claim**, embedding the numeric owner ID (`102995309`) and
repo ID (`1303961107`). Everything else was fine — provider found, role found, token valid.

**Fix:** trust policy now accepts both forms via a `StringLike` array. No wildcards; both
entries exact; still pinned to this repo and `main` only.

---
