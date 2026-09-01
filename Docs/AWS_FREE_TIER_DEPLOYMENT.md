# AWS Free Tier Deployment Roadmap — Taxify

**Budget:** $0. Every resource below sits inside the AWS Free Tier (12-month + always-free).
**Scope:** Single environment. No staging/prod split, no autoscaling.
CI/CD via GitHub Actions (§10) — not an AWS resource, does not touch the free tier.
**Last updated:** 2026-08-24

---``

## 1. Stack identified (from the repo)

| # | Item | Detail | Source |
|---|---|---|---|
| 1.1 | Backend | FastAPI + uvicorn, Python **3.10** | `run.py` |
| 1.2 | Entry point | binds `127.0.0.1:8000`, `reload=True`, `loop="none"` | `run.py:65-71` |
| 1.3 | Database | **SQLite**, hardcoded — no RDS needed | `app/db/database.py:11` |
| 1.4 | Frontend | React 19 + Vite 8 + TypeScript → static `dist/` | `frontend/package.json` |
| 1.5 | API base URL | `VITE_API_BASE_URL`, default `http://localhost:8000` — **baked in at build time** | `frontend/src/api/axiosInstance.ts:4` |
| 1.6 | Automation | Playwright; prefers real Chrome (`channel="chrome"`), falls back to bundled Chromium | `app/automation/browser.py:199,210` |
| 1.7 | PDF | PyMuPDF (`fitz`) + pikepdf — native wheels, install on Linux | `requirements.txt` |
| 1.8 | Ports | 8000 backend, 3000 frontend dev, 80/443 nginx in prod | `frontend/vite.config.ts` |
| 1.9 | Java | **Not** in the Python path; `API_Testing/` tooling is standalone | — |

---

## 2. Blockers to resolve before provisioning

> **RESOLVED — ITD IP whitelisting.** The source-IP dependency that used to require a
> whitelisted-egress jump host (`3.108.145.216`) has been
> **eliminated**. ERI endpoints no longer require the deployment IP to be whitelisted, so a
> fresh EC2 instance with any public IP can reach them. No paperwork dependency, no jump-host
> egress requirement, no provisioning order constraint.

### 2.1 Stale Type-2 startup guard will block boot
The *network* reason for the SSH jump host is gone, but the **code guard remains**.
`app/eri/config.py:197-201` raises `RuntimeError` at app startup (called from the
`app/main.py` lifespan) whenever `ERI_ENV=production` **and** `ERI_MODE=type2`:

```
ERI_AWS_SSH_HOST_TYPE2_PRODUCTION is required for Type-2 production (whitelisted-IP egress).
```

The app will refuse to start. Three options, best first:

1. **Remove the now-obsolete guard** at `app/eri/config.py:197-201` — its stated rationale
   ("whitelisted-IP egress") no longer applies. Cleanest, and costs nothing.
2. Run `ERI_MODE=type3` — that branch has no SSH requirement at all.
3. Set a dummy `ERI_AWS_SSH_HOST_TYPE2_PRODUCTION` value. **Not recommended** — it leaves a
   misleading config key implying an egress path that isn't used.

Note the guard only fires for Type-2 **production**. Type-2 UAT and all Type-3 modes start fine.

### 2.2 Interactive browser flows need a virtual display
`app/automation/browser.py:216` launches a *visible* Chrome for interactive jobs
(ack-download). EC2 has no display.

**Free alternative:** `xvfb` (apt, free); run the service under `xvfb-run`. See §6.8.

### 2.3 1 GB RAM will OOM without swap
Chrome + uvicorn + `tsc` exceeds t3.micro memory. A swap file is **mandatory** (§6.3).
Swap lives on EBS and is free within the 30 GB allowance.

---

## 3. Free tier resource ledger

| # | Resource | Free tier limit | Expected usage | Verdict |
|---|---|---|---|---|
| 3.1 | EC2 t3.micro (or t2.micro) | 750 hrs/mo, 12 mo | 744 hrs (1 instance, always on) | ✅ within |
| 3.2 | EBS **gp3** root volume | 30 GB, 12 mo | ~15 GB (OS 3 + Chrome 0.4 + venv 0.8 + swap 2 + data) | ✅ within |
| 3.3 | Public IPv4 (Elastic IP) | 750 hrs/mo, **12 mo only** | 744 hrs | ⚠️ see §4.1 |
| 3.4 | Data transfer out | 100 GB/mo | Low (JSON API + ~2 MB static bundle) | ✅ within |
| 3.5 | EBS snapshots | 1 GB free | 0 — take none | ✅ skip |
| 3.6 | CloudWatch | 10 default metrics, 5 GB logs | Default metrics only, no alarms | ✅ within |
| 3.7 | VPC / Subnet / IGW / Route table / SG | Always free | 1 each | ✅ free |
| 3.8 | Key pair | Always free | 1 | ✅ free |

### Deliberately NOT used

| Service | Reason | Free-tier-safe substitute |
|---|---|---|
| RDS | SQLite suffices (§1.3) | — |
| S3 | Avoids a second resource | nginx serves `dist/` from the same box |
| **ALB / ELB** | **Not free at any tier** | nginx terminates TLS on the instance |
| **NAT Gateway** | **Not free** | public subnet + security group |
| **Route 53** | **Not free** | DuckDNS (§5.9) |
| Elastic Beanstalk / ECS / Fargate / Lightsail | More resources than a single EC2 | plain EC2 |
| Secrets Manager | $0.40/secret/mo | 600-mode env file (§7.2) |

### Why gp3, not gp2 — the single highest-impact free choice

Both are covered by the same 30 GB "General Purpose (SSD)" allowance, so gp3 costs nothing extra.
But **gp2 IOPS scale with volume size at 3 IOPS/GB** — a 16 GB gp2 volume gets **48 baseline
IOPS**, which is catastrophic for a swap file and for SQLite's write path. **gp3 delivers 3,000
baseline IOPS regardless of size.** On a 1 GB box that swaps, this one flag matters more than
every other tuning decision in this document.

---

## 4. Where free tier can break — and the guard

| # | Risk | Guard |
|---|---|---|
| 4.1 | **Public IPv4 after month 12.** Since 2024-02-01 AWS bills every public IPv4 at $0.005/hr. Free tier covers 750 hrs/mo for **12 months only**. From month 13: **~$3.60/mo, unavoidable** while reachable. | Calendar reminder at month 11 — accept the charge or tear down. |
| 4.2 | **Unattached Elastic IP bills immediately**, even in year 1. | Never release the instance while keeping the EIP. Teardown order in §9 handles this. |
| 4.3 | **A second instance silently doubles hours.** 750 ÷ 2 = 375 hrs each, then billing. | Never run two. Stop one before testing another. |
| 4.4 | **Instance type drift.** Only `t2.micro`/`t3.micro` are free; `t3.small` is not. | Pin the type in the CLI command; never resize. |
| 4.5 | **EBS creep past 30 GB.** Playwright may re-download browsers per profile; `downloads/` grows per client PDF. | Pin `PLAYWRIGHT_BROWSERS_PATH` system-wide (§6.6) + cron prune (§6.11). |
| 4.6 | **Data transfer out >100 GB/mo.** Only plausible when serving large PDFs at volume. | `du -sh downloads/` monthly. |
| 4.7 | **Forgetting to stop it.** 744 < 750 hrs, so one always-on instance is fine — but only one. | Same as 4.3. |
| 4.8 | **CloudWatch alarms are not free** beyond default metrics. | Create none. Use **AWS Budgets** (free) instead — §5.8. |
| 4.9 | **⚠️ T3 burstable credits — the easiest way to get billed on "free" infra.** T3 instances launch in **`unlimited`** CPU-credit mode **by default**. Exceed the 10%/vCPU baseline and AWS bills surplus credits — **free tier does not cover this**. Playwright/Chrome is exactly the spiky-CPU workload that triggers it. | Launch with `--credit-specification CpuCredits=standard` (§5.6). In `standard` mode the instance throttles instead of billing — it can never produce a charge. T2 defaults to `standard` already, but gives 1 vCPU instead of 2. |

---

## 5. Provisioning (AWS CLI, in order)

```bash
# 5.1 Vars — pick a region near you
export AWS_REGION=ap-south-1
export NAME=taxify

# 5.2 Default VPC + public subnet (free; no NAT)
export VPC_ID=$(aws ec2 describe-vpcs --region $AWS_REGION \
  --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
export SUBNET_ID=$(aws ec2 describe-subnets --region $AWS_REGION \
  --filters Name=vpc-id,Values=$VPC_ID Name=default-for-az,Values=true \
  --query 'Subnets[0].SubnetId' --output text)

# 5.3 Key pair
aws ec2 create-key-pair --region $AWS_REGION --key-name $NAME-key \
  --query 'KeyMaterial' --output text > ~/.ssh/$NAME-key.pem
chmod 400 ~/.ssh/$NAME-key.pem

# 5.4 Security group — SSH restricted to your IP only
export MYIP=$(curl -s https://checkip.amazonaws.com)
export SG_ID=$(aws ec2 create-security-group --region $AWS_REGION \
  --group-name $NAME-sg --description "$NAME" --vpc-id $VPC_ID \
  --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --region $AWS_REGION --group-id $SG_ID \
  --protocol tcp --port 22 --cidr $MYIP/32
aws ec2 authorize-security-group-ingress --region $AWS_REGION --group-id $SG_ID \
  --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --region $AWS_REGION --group-id $SG_ID \
  --protocol tcp --port 443 --cidr 0.0.0.0/0
# Do NOT open 8000 — nginx proxies to it on localhost.

# 5.5 Ubuntu 22.04 LTS AMI (ships Python 3.10 — matches the working interpreter)
export AMI_ID=$(aws ssm get-parameters --region $AWS_REGION \
  --names /aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id \
  --query 'Parameters[0].Value' --output text)

# 5.6 Launch — free type, 16 GB gp3, CPU credits pinned to standard
export INSTANCE_ID=$(aws ec2 run-instances --region $AWS_REGION \
  --image-id $AMI_ID --instance-type t3.micro --key-name $NAME-key \
  --credit-specification CpuCredits=standard \
  --security-group-ids $SG_ID --subnet-id $SUBNET_ID \
  --associate-public-ip-address \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":16,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
  --query 'Instances[0].InstanceId' --output text)
aws ec2 wait instance-running --region $AWS_REGION --instance-ids $INSTANCE_ID

# 5.6b VERIFY credit mode — this is the one setting that can silently bill you (§4.9)
aws ec2 describe-instance-credit-specifications --region $AWS_REGION \
  --instance-ids $INSTANCE_ID --query 'InstanceCreditSpecifications[0].CpuCredits'
# MUST print "standard". If it prints "unlimited", fix it immediately:
#   aws ec2 modify-instance-credit-specification --region $AWS_REGION \
#     --instance-credit-specifications "InstanceId=$INSTANCE_ID,CpuCredits=standard"

# 5.7 Elastic IP — keeps the DuckDNS A record stable across stop/start
export ALLOC_ID=$(aws ec2 allocate-address --region $AWS_REGION --domain vpc \
  --query 'AllocationId' --output text)
aws ec2 associate-address --region $AWS_REGION \
  --instance-id $INSTANCE_ID --allocation-id $ALLOC_ID
export PUBLIC_IP=$(aws ec2 describe-addresses --region $AWS_REGION \
  --allocation-ids $ALLOC_ID --query 'Addresses[0].PublicIp' --output text)
echo "PUBLIC IP (point DuckDNS at this): $PUBLIC_IP"
echo "$INSTANCE_ID $ALLOC_ID $SG_ID" > ~/.taxify-aws-ids   # keep for teardown
```

> An auto-assigned public IP is billed identically to an Elastic IP ($0.005/hr, same 750 free
> hrs), so the EIP costs nothing extra. Its only job here is keeping the DNS record stable —
> without it, a stop/start hands you a new IP and DuckDNS needs re-pointing every time.

### 5.8 Budget guard (free)

```bash
cat > /tmp/budget.json <<'EOF'
{"BudgetName":"taxify-zero","BudgetLimit":{"Amount":"1","Unit":"USD"},
 "TimeUnit":"MONTHLY","BudgetType":"COST"}
EOF
cat > /tmp/notify.json <<'EOF'
[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN",
  "Threshold":1,"ThresholdType":"PERCENTAGE"},
  "Subscribers":[{"SubscriptionType":"EMAIL","Address":"you@example.com"}]}]
EOF
aws budgets create-budget --account-id ACCOUNT_ID \
  --budget file:///tmp/budget.json \
  --notifications-with-subscribers file:///tmp/notify.json
```

### 5.9 Free DNS — DuckDNS (already registered)

**Domain:** `www.taxbharo.duckdns.org`
**Currently points at:** `106.192.216.31` — this is *not* an AWS address, so it must be
re-pointed at the Elastic IP from §5.7 before TLS issuance will succeed.

```bash
# Re-point DuckDNS at the EC2 Elastic IP. Token is on your duckdns.org account page.
export DUCKDNS_TOKEN=<your-duckdns-token>
curl "https://www.duckdns.org/update?domains=taxbharo&token=$DUCKDNS_TOKEN&ip=$PUBLIC_IP"
# expect: OK

# Verify propagation before running certbot
dig +short taxbharo.duckdns.org
dig +short www.taxbharo.duckdns.org     # DuckDNS wildcards subdomains to the same A record
# both must return $PUBLIC_IP
```

A domain is needed because **Let's Encrypt will not issue a certificate for a bare IP**.
`nip.io` / `sslip.io` hit LE rate limits; DuckDNS is the reliable free choice.

> DuckDNS resolves `*.taxbharo.duckdns.org` to the same A record as the apex, so both
> `taxbharo.duckdns.org` and `www.taxbharo.duckdns.org` work off the single update call above.
> Certificates in §6.10 cover both names.

---

## 6. Deployment on the instance

```bash
ssh -i ~/.ssh/taxify-key.pem ubuntu@$PUBLIC_IP
```

### 6.1–6.2 Base packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.10 python3.10-venv python3-pip git nginx xvfb \
  build-essential libpq-dev sqlite3 unzip

curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 6.3 Swap — mandatory on 1 GB (ref §2.3)

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h   # confirm 2Gi swap
```

### 6.4–6.5 Code and Python env

```bash
sudo mkdir -p /opt/taxify && sudo chown ubuntu:ubuntu /opt/taxify
git clone <your-repo-url> /opt/taxify && cd /opt/taxify

python3.10 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

# requirements.txt under-declares — these are imported but missing:
./.venv/bin/pip install email-validator httpx urllib3 pytest-asyncio
```

### 6.6 Playwright + Chrome

```bash
export PLAYWRIGHT_BROWSERS_PATH=/opt/taxify/.playwright
echo 'PLAYWRIGHT_BROWSERS_PATH=/opt/taxify/.playwright' | sudo tee -a /etc/environment

# Install ONLY Chrome — browser.py:199 prefers channel="chrome".
# Installing bundled Chromium too wastes ~450 MB and is never reached on the happy path.
./.venv/bin/playwright install-deps
./.venv/bin/playwright install --with-deps chrome
```

> **Optimisation — don't install both browsers.** `browser.py:199` launches
> `channel="chrome"` and only falls back to bundled Chromium at `:210` *by catching an
> exception*. If Chrome is present, Chromium is dead weight on disk; if Chrome is absent, you
> pay an exception on **every single launch**. Pick one — Chrome, since that's what the code
> prefers. Install Chromium instead only if you patch the preference out.

### 6.7 Frontend build

`VITE_API_BASE_URL` is baked in at build time (§1.5) — set it before building.

> **Optimisation — build in CI, not on the box.** `tsc -b && vite build` on 1 GB RAM runs
> through EBS-backed swap; it is slow and can still OOM. The output is byte-identical wherever
> you build it, so there is no reason to spend the box's scarce memory on it. **§10 replaces
> this step entirely.** Use the commands below only for the very first bootstrap, or if you
> skip CI/CD.

```bash
# Bootstrap-only path (superseded by §10)
cd /opt/taxify/frontend
echo "VITE_API_BASE_URL=https://www.taxbharo.duckdns.org" > .env.production
npm ci
NODE_OPTIONS=--max-old-space-size=1536 npm run build   # needs the swap from 6.3

# Node is only needed to build. If CI builds for you (§10), reclaim ~200 MB:
#   sudo apt remove -y nodejs && sudo apt autoremove -y
```

### 6.8 systemd unit — survives reboot and SSH disconnect

```bash
sudo tee /etc/systemd/system/taxify.service >/dev/null <<'EOF'
[Unit]
Description=Taxify FastAPI
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/taxify
EnvironmentFile=/etc/taxify/taxify.env
Environment=PLAYWRIGHT_BROWSERS_PATH=/opt/taxify/.playwright
# xvfb-run supplies a virtual display for the visible-Chrome path (browser.py:216)
ExecStart=/usr/bin/xvfb-run -a /opt/taxify/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5

# --- 1 GB survival tuning ---
# Cap the cgroup so a leaked Chrome cannot get uvicorn OOM-killed instead of itself.
MemoryMax=750M
MemoryHigh=650M
# Kill the whole cgroup (including orphaned Chrome children) on stop/restart.
KillMode=control-group
TimeoutStopSec=30
OOMPolicy=continue

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now taxify
sudo systemctl status taxify --no-pager
```

> **Why not `run.py`?** `run.py` sets `WindowsProactorEventLoopPolicy` and `loop="none"` purely
> to dodge a **Windows-only** asyncio trap. On Linux the default loop already supports
> subprocesses, so Playwright works fine under plain uvicorn.
>
> **Why `--workers 1`?** `browser.py` holds a **singleton** browser (`_browser`, `_headless`),
> which is not safe across worker processes. This also means extra RAM would buy you no
> API concurrency — the ceiling is the singleton, not the memory.
>
> **Why `MemoryMax`/`KillMode=control-group`?** Playwright leaks Chrome processes when a job
> crashes mid-flight, and the singleton survives across jobs. Without a cgroup cap, the kernel
> OOM-killer picks uvicorn (the largest RSS) rather than the leaked browser, taking the whole
> API down. With the cap, the leak is contained and `systemctl restart` reaps every child.

### 6.9–6.10 nginx + free TLS

nginx replaces an ALB for $0.

```bash
sudo tee /etc/nginx/sites-available/taxify >/dev/null <<'EOF'
server {
    listen 80;
    server_name www.taxbharo.duckdns.org taxbharo.duckdns.org;
    client_max_body_size 25M;          # ITR PDFs

    # Compression — cuts the JS/CSS bundle ~70% on the wire, saving both
    # page-load time and the 100 GB/mo transfer allowance (§4.6).
    gzip on;
    gzip_comp_level 6;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_types text/plain text/css application/javascript application/json
               image/svg+xml application/xml font/woff2;

    root /opt/taxify/frontend/dist;
    index index.html;

    # Vite emits content-hashed filenames, so assets are safe to cache forever.
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    # index.html must NEVER be cached, or clients pin a stale bundle after deploy.
    location = /index.html {
        add_header Cache-Control "no-store, must-revalidate";
    }
    location / { try_files $uri $uri/ /index.html; }

    location ~ ^/(auth|clients|eri|filing|automation|integration|health) {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 600s;       # portal automation jobs are slow
    }
}
EOF
sudo ln -sf /etc/nginx/sites-available/taxify /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Free TLS — requires §5.9 DNS to already resolve to $PUBLIC_IP (HTTP-01 challenge)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx \
  -d www.taxbharo.duckdns.org -d taxbharo.duckdns.org \
  --agree-tos -m you@example.com --redirect
sudo systemctl list-timers | grep certbot   # auto-renew installed by the package
```

### 6.11 Disk guard (ref §4.5) and orphaned-Chrome reaper

```bash
(crontab -l 2>/dev/null
 echo '0 3 * * * find /opt/taxify/downloads -type f -mtime +30 -delete'
 # Reap Chrome processes older than 2h with no live job — Playwright leaks these
 # on mid-flight job crashes, and each one costs ~150 MB of a 1 GB box.
 echo '*/30 * * * * pkill -f "chrome.*--headless" --older-than 7200 2>/dev/null || true'
) | crontab -
```

### 6.12 CORS

`app/main.py:122` defaults to localhost origins only. Set `CORS_ALLOWED_ORIGINS` to the real
origin — see §7.4.

### 6.13 SQLite concurrency — required, not optional

`app/db/database.py:15-18` sets only `check_same_thread=False`. It does **not** enable WAL, so
the database runs in default `delete` journal mode where **a writer blocks all readers**. The
background automation worker writes job state while the API serves reads, so under concurrent
import jobs you will hit `sqlite3.OperationalError: database is locked`.

Free fix — add to `app/db/database.py`:

```python
from sqlalchemy import event

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)

@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")     # readers no longer block on writers
    cur.execute("PRAGMA busy_timeout=5000")    # wait 5s for a lock instead of failing
    cur.execute("PRAGMA synchronous=NORMAL")   # safe with WAL, far fewer fsyncs
    cur.close()
```

`synchronous=NORMAL` matters on EBS specifically: every fsync is a network round-trip, and WAL
makes NORMAL durable against application crashes (only a host power-loss can lose the last
transaction). Verify after deploy with `sqlite3 app.db "PRAGMA journal_mode;"` → `wal`.

---

## 7. Env vars and secrets — never committed

7.1. `.env` is already gitignored (`.gitignore:19`). **Keep it that way — it holds live ERI
production credentials.** Never `git add -f` it.

7.2. Create the file **directly on the server**, root-owned, mode 600:

```bash
sudo mkdir -p /etc/taxify
sudo touch /etc/taxify/taxify.env
sudo chmod 600 /etc/taxify/taxify.env
sudo chown root:root /etc/taxify/taxify.env
sudo nano /etc/taxify/taxify.env     # paste values, no quotes, KEY=value
sudo ln -s /etc/taxify/taxify.env /opt/taxify/.env   # the app also calls load_dotenv()
```

### 7.3 Required keys (38 total)

**App**
`SECRET_KEY`, `PORTAL_ENCRYPTION_KEY`, `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`

**ERI selectors**
`ERI_MODE`, `ERI_ENV`, `ERI_INTERMEDIARY_CITY`, `ERI_DSC_SIGNING_MODE`, `ERI_SYMMETRIC_KEY`

**Type-2** (each ×`_UAT` and ×`_PRODUCTION`)
`ERI_BASE_URL_`, `ERI_CLIENT_ID_`, `ERI_CLIENT_SECRET_`, `ERI_USER_ID_`, `ERI_PASSWORD_`,
`ERI_SW_ID_`, `ERI_DIGEST_SECRET_KEY_`, `ERI_DIGEST_ITERATIONS_`, `ERI_AWS_SSH_HOST_`,
`ERI_AWS_SSH_USER_`, `ERI_AWS_SSH_KEY_PATH_`

**Type-3** (each ×`_UAT` and ×`_PRODUCTION`)
`ERI_USER_ID_`, `ERI_SW_ID_`, `ERI_DIGEST_SECRET_KEY_`, `ERI_DIGEST_ITERATIONS_`

7.4. Set `FRONTEND_URL=https://www.taxbharo.duckdns.org` and
`CORS_ALLOWED_ORIGINS=https://www.taxbharo.duckdns.org,https://taxbharo.duckdns.org`
(`app/main.py:122` splits this on commas).

7.5. **Rotate `SECRET_KEY` and `PORTAL_ENCRYPTION_KEY` for the server** — do not reuse dev
values. Rotating `PORTAL_ENCRYPTION_KEY` invalidates stored portal passwords;
`scripts/regen_portal_key.py` and `scripts/clear_broken_portal_passwords.py` exist for this.

7.6. **Skip AWS Secrets Manager** — not free ($0.40/secret/mo). SSM Parameter Store *Standard*
is free if you prefer it over a file, but a 600-mode file is simpler and costs nothing.

7.7. **Transfer `app.db` to keep existing users:**
`scp -i ~/.ssh/taxify-key.pem app.db ubuntu@$PUBLIC_IP:/opt/taxify/app.db`
Otherwise tables auto-create on first run.

---

## 8. Verify

| # | Check | Expected |
|---|---|---|
| 8.1 | `sudo systemctl is-active taxify nginx` | both `active` |
| 8.2 | `curl -I http://127.0.0.1:8000/docs` (on the box) | `200` |
| 8.3 | Browse `https://www.taxbharo.duckdns.org` | app loads, login works |
| 8.4 | `sudo reboot`, wait 60 s, re-check 8.1 | confirms restart survival |
| 8.5 | `free -h` | swap in use, not exhausted |
| 8.6 | Trigger one import job; `journalctl -u taxify -f` | Playwright launches, job completes |
| 8.7 | One live ERI call in the target `ERI_MODE`/`ERI_ENV` | succeeds — no IP whitelisting needed |
| 8.8 | Day 2: Billing → Free Tier page | all lines <100% |

---

## 9. Teardown checklist

> Covers the CI/CD IAM objects from §10 as well (step 9.5b) — run this whole list even if you
> never set CI/CD up; the extra commands no-op harmlessly.

```bash
source ~/.taxify-aws-ids   # or re-read the IDs saved in 5.7
export AWS_REGION=ap-south-1

# 9.1 Back up data FIRST — terminating destroys the EBS volume
scp -i ~/.ssh/taxify-key.pem ubuntu@$PUBLIC_IP:/opt/taxify/app.db ./app.db.backup
scp -i ~/.ssh/taxify-key.pem -r ubuntu@$PUBLIC_IP:/opt/taxify/downloads ./downloads.backup

# 9.2 Terminate instance
aws ec2 terminate-instances --region $AWS_REGION --instance-ids $INSTANCE_ID
aws ec2 wait instance-terminated --region $AWS_REGION --instance-ids $INSTANCE_ID

# 9.3 RELEASE the Elastic IP — the #1 forgotten charge (ref §4.2)
aws ec2 release-address --region $AWS_REGION --allocation-id $ALLOC_ID

# 9.4 Delete security group (only after the instance is fully terminated)
aws ec2 delete-security-group --region $AWS_REGION --group-id $SG_ID

# 9.5 Delete key pair
aws ec2 delete-key-pair --region $AWS_REGION --key-name taxify-key

# 9.5b Remove CI/CD IAM objects (§10) — all free, but leave no orphans
aws iam remove-role-from-instance-profile \
  --instance-profile-name taxify-ssm --role-name taxify-ssm
aws iam delete-instance-profile --instance-profile-name taxify-ssm
aws iam detach-role-policy --role-name taxify-ssm \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam delete-role --role-name taxify-ssm
aws iam delete-role --role-name taxify-gha-deploy 2>/dev/null || true

# 9.6 Confirm NOTHING remains
aws ec2 describe-instances --region $AWS_REGION \
  --filters Name=instance-state-name,Values=running,stopped \
  --query 'Reservations[].Instances[].InstanceId'                        # expect []
aws ec2 describe-addresses --region $AWS_REGION --query 'Addresses[]'    # expect []
aws ec2 describe-volumes --region $AWS_REGION \
  --filters Name=status,Values=available --query 'Volumes[].VolumeId'    # expect [] — orphans bill
aws ec2 describe-snapshots --region $AWS_REGION --owner-ids self \
  --query 'Snapshots[].SnapshotId'                                       # expect []
```

9.7. **Check every region** — orphans hide in regions you forgot:

```bash
for r in $(aws ec2 describe-regions --query 'Regions[].RegionName' --output text); do
  echo "== $r"
  aws ec2 describe-instances --region $r \
    --filters Name=instance-state-name,Values=running \
    --query 'Reservations[].Instances[].InstanceId' --output text
done
```

9.8. Delete the budget:
`aws budgets delete-budget --account-id ACCOUNT_ID --budget-name taxify-zero`

9.9. Delete the free DuckDNS subdomain at duckdns.org (costs nothing either way).

9.10. Disable the GitHub Actions workflow (§10.5) so it stops firing against a dead instance —
delete `.github/workflows/deploy.yml` or disable it in the repo's Actions tab. It costs nothing
either way, but every push would otherwise fail loudly.

9.11. Confirm at **Billing → Bills** 24–48 h later that month-to-date is **$0.00**.

---

## 10. CI/CD — $0, and not an AWS resource

**Key point: GitHub Actions has its own free allowance and never touches the AWS free tier.**
This also removes the frontend build from the 1 GB box entirely (§6.7), which is the largest
single efficiency win available.

### 10.1 CI/CD budget ledger

| Component | Free allowance | Expected usage | Cost |
|---|---|---|---|
| GitHub Actions | 2,000 min/mo private · **unlimited public** | ~3 min/deploy | $0 |
| GitHub Releases / Artifacts | 500 MB private storage | ~2 MB bundle | $0 |
| AWS SSM Run Command | Always free | ~1 call/deploy | $0 |
| IAM role + instance profile | Always free | 2 | $0 |
| GitHub OIDC → IAM | Always free | 1 provider | $0 |

> Confirm repo visibility: public repos get **unlimited** Actions minutes; private repos get
> 2,000/mo. At ~3 min per deploy, even 100 deploys/month uses 300 min. Either way it is free.

### 10.2 Architecture

```
push to main
   ↓
GH Actions: npm ci && npm run build        ← the 1 GB box never builds anything
   ↓
upload dist.tar.gz as a GitHub Release asset   ← no S3 needed, AWS stays at 1 resource
   ↓
aws ssm send-command  (auth via OIDC, no long-lived AWS keys)
   ↓
EC2: pull tarball → extract dist/ → git pull backend → systemctl restart taxify
```

**Why SSM instead of SSH deploy.** The security group locks port 22 to your home IP (§5.4).
GitHub runners have rotating IPs, so an SSH deploy forces you to either open 22 to
`0.0.0.0/0` or maintain a runner allowlist — both bad. **SSM Run Command is outbound-only**:
the agent (pre-installed on the Ubuntu AMI) dials out, so port 22 stays locked to you and
deploys still work. Free, and needs only `AmazonSSMManagedInstanceCore` on an instance profile.

**Why OIDC instead of AWS access keys in GitHub Secrets.** Short-lived credentials, nothing
long-lived to leak. Worth the extra setup given this repo's `.env` holds live ERI production
credentials.

**Why GitHub Releases instead of S3.** Keeps the AWS resource count at exactly one. S3 would
fit the free tier, but there is no reason to add a resource for a 2 MB bundle.

### 10.3 Attach the SSM instance profile (one-time, free)

```bash
aws iam create-role --role-name taxify-ssm \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam attach-role-policy --role-name taxify-ssm \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam create-instance-profile --instance-profile-name taxify-ssm
aws iam add-role-to-instance-profile \
  --instance-profile-name taxify-ssm --role-name taxify-ssm
aws ec2 associate-iam-instance-profile --region $AWS_REGION \
  --instance-id $INSTANCE_ID --iam-instance-profile Name=taxify-ssm

# Confirm the instance appears as a managed node (may take ~2 min)
aws ssm describe-instance-information --region $AWS_REGION \
  --query 'InstanceInformationList[].InstanceId'
```

### 10.4 Deploy script on the box

```bash
sudo tee /opt/taxify/deploy.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/taxify

git fetch --all --prune
git reset --hard origin/main

# Only reinstall Python deps when they actually changed
if ! git diff --quiet HEAD@{1} HEAD -- requirements.txt 2>/dev/null; then
  ./.venv/bin/pip install -r requirements.txt
fi

# Prebuilt frontend from the GitHub Release — no npm/tsc on this box
TAG="${1:-latest}"
curl -fsSL -o /tmp/dist.tar.gz \
  "https://github.com/DevanshGoyanka/Taxify/releases/download/${TAG}/dist.tar.gz"
rm -rf /opt/taxify/frontend/dist
mkdir -p /opt/taxify/frontend/dist
tar -xzf /tmp/dist.tar.gz -C /opt/taxify/frontend/dist
rm -f /tmp/dist.tar.gz

sudo systemctl restart taxify
sleep 3
systemctl is-active --quiet taxify || { echo "SERVICE FAILED TO START"; exit 1; }
echo "deployed ${TAG}"
EOF
sudo chmod +x /opt/taxify/deploy.sh
sudo chown ubuntu:ubuntu /opt/taxify/deploy.sh
```

### 10.5 Workflow — `.github/workflows/deploy.yml`

```yaml
name: deploy
on:
  push:
    branches: [main]

permissions:
  contents: write      # create the Release
  id-token: write      # request the OIDC token

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Build frontend
        working-directory: frontend
        env:
          VITE_API_BASE_URL: https://www.taxbharo.duckdns.org
        run: |
          npm ci
          npm run build
          tar -czf ../dist.tar.gz -C dist .

      - name: Publish release asset
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          TAG="build-${GITHUB_RUN_NUMBER}"
          gh release create "$TAG" dist.tar.gz --notes "Auto build ${GITHUB_SHA::7}"
          echo "TAG=$TAG" >> $GITHUB_ENV

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT_ID:role/taxify-gha-deploy
          aws-region: ap-south-1

      - name: Deploy via SSM
        run: |
          CMD=$(aws ssm send-command \
            --instance-ids ${{ secrets.EC2_INSTANCE_ID }} \
            --document-name AWS-RunShellScript \
            --parameters "commands=['sudo -u ubuntu /opt/taxify/deploy.sh $TAG']" \
            --query 'Command.CommandId' --output text)
          aws ssm wait command-executed \
            --command-id "$CMD" --instance-id ${{ secrets.EC2_INSTANCE_ID }} || true
          aws ssm get-command-invocation \
            --command-id "$CMD" --instance-id ${{ secrets.EC2_INSTANCE_ID }} \
            --query '{Status:Status,Out:StandardOutputContent,Err:StandardErrorContent}'
```

### 10.6 Test gating — be realistic

**Do not gate merges on the full suite yet.** A measured baseline run at `af6cfc5` produced
**177 failures and 13 collection errors**, none caused by deployment work. A required check
that is red on day one gets bypassed within a week, and then you have CI theatre.

Ratchet up instead:

1. **Now** — CI runs build + lint only. Deploy on green build. No test gate.
2. **Next** — add the four missing runtime deps to `requirements.txt`:
   `email-validator`, `httpx`, `urllib3`, `pytest-asyncio`. The last one matters most:
   `pytest.ini` sets `asyncio_mode = auto`, but pytest reports it as an **unknown config
   option**, so async tests are not running as designed. This alone may clear a large slice
   of the 177.
3. **Then** — gate on a curated green subset as a required check
   (`test_itr1_calculator`, `test_itr4_calculator`, `test_itr1_schemas`, …).
4. **Later** — expand the subset as suites go green. Ratchet up, never down.

### 10.7 Simpler fallback — pull-based deploy

If OIDC + SSM is more setup than you want, run a systemd timer on the box:

```bash
# every 5 min: if origin/main moved, run deploy.sh
sudo tee /etc/systemd/system/taxify-deploy.timer >/dev/null <<'EOF'
[Unit]
Description=Poll for new Taxify builds
[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
EOF
```

Zero secrets, zero AWS IAM, zero inbound ports. Costs you ~5 min deploy latency and gives no
PR feedback. The box-side `deploy.sh` is identical either way, so starting here and graduating
to §10.5 later is cheap.

### 10.8 CI/CD approaches to avoid

| Approach | Why not |
|---|---|
| **CodePipeline / CodeBuild** | Free tier is 1 pipeline + 100 build-min/mo — tight, AWS-billed, real charges on overage. Actions is more generous and safer under a hard $0 constraint. |
| **Docker / ECR** | ECR free tier is 500 MB for **12 months only**, and container overhead on a 1 GB box competing with Chrome is a bad trade. |
| **Self-hosted GH runner on the EC2** | Tempting (unlimited minutes) but it consumes the same 1 GB you need for Chrome and contends with live automation jobs. The one "clever" optimisation that actively makes things worse here. |

---

## 11. Known non-free items

One item could not be made free:

1. **Public IPv4 after month 12** (§4.1) — ~$3.60/mo, unavoidable while the box is reachable.
   Applies equally to an Elastic IP and an auto-assigned one.

Everything else sits inside the free tier as listed in §3.

*(The ITD IP-whitelisting dependency previously listed here has been eliminated — see the note
at the top of §2.)*
