# Taxify Production Runbook

Condensed operational reference for the live deployment.
Full history: `docs/deployment-log.md` · Resources: `docs/resource-inventory.md` · Teardown: `docs/teardown.md`

| | |
|---|---|
| **URL** | https://itrbharo.duckdns.org |
| **Public IP** | `43.205.225.117` (Elastic IP — survives stop/start) |
| **Instance** | `i-06fa754bdb98c95af` · t3.micro · ap-south-1c |
| **AWS account** | `938509046486` · CLI profile **`myuser`** |
| **App root** | `/opt/taxify` (branch `main`) |
| **Runs as** | `ubuntu` |
| **ERI mode** | Type-3 **UAT** (`SW20014243`) |

---

## Getting a shell — SSM, not SSH

**Port 22 is closed to the internet.** Access is via AWS Systems Manager, which connects
*outbound* from the instance through the AWS API. There is no inbound port to attack, and no IP
allowlist to maintain.

### Why SSH was abandoned

The security group pinned port 22 to a single `/32`. Your ISP uses **Carrier-Grade NAT**: a
pool of exit addresses shared by many customers, where *different connections leave through
different IPs at the same moment*. Two probes one second apart returned `42.104.221.14` and
`42.104.220.7`. Your address changed three times in one day
(`106.192.216.31` → `106.221.215.87` → `42.104.220.7`).

A `/32` rule can never be stable under CGNAT — authorising the IP you *see* does not guarantee
the IP your SSH connection *uses*. SSM removes the problem rather than working around it.

> The **Elastic IP `43.205.225.117` is the server's** address and never changes. Your laptop's
> address is what the firewall rule filters on. Two different things — the site stayed up for
> everyone the entire time SSH was broken.

### Option A — browser shell (no install)

AWS Console → **Systems Manager** → **Session Manager** → **Start session** →
select `i-06fa754bdb98c95af`. Works from anywhere, nothing to install.

### Option B — CLI shell (needs a one-time plugin install)

```powershell
aws ssm start-session --profile myuser --region ap-south-1 --target i-06fa754bdb98c95af
```

Requires the **Session Manager plugin** (not currently installed):
<https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html>

### Option C — run a script without a shell

```powershell
aws ssm send-command --profile myuser --region ap-south-1 `
  --instance-ids i-06fa754bdb98c95af `
  --document-name AWS-RunShellScript `
  --parameters 'commands=["systemctl is-active taxify","df -h /"]' `
  --query 'Command.CommandId' --output text

# then fetch the output
aws ssm get-command-invocation --profile myuser --region ap-south-1 `
  --command-id <ID> --instance-id i-06fa754bdb98c95af `
  --query '{Status:Status,Out:StandardOutputContent,Err:StandardErrorContent}'
```

### First 30 seconds in an SSM shell — read this

A Session Manager shell is **not** an SSH session. Three things differ, and they trip everyone
up immediately:

| | SSM session | What you probably expect |
|---|---|---|
| User | `ssm-user` (uid 1001) | `ubuntu` |
| Landing dir | `/home/ssm-user` — **empty**, so `ls` prints nothing | the app directory |
| Shell | `/bin/sh` (**dash**, not bash) | bash |

So a bare `cd taxify` fails — there is no relative path to it:

```sh
$ ls                      # nothing: /home/ssm-user is empty
$ cd taxify
sh: 4: cd: can't cd to taxify
```

Use the absolute path, and switch to the account that owns the app:

```sh
sudo su - ubuntu          # ssm-user has passwordless sudo
cd /opt/taxify
```

Prefer bash for history/tab-completion (dash has neither):

```sh
bash
```

**`Ctrl-C` does not end the session** — it interrupts the running command. Type `exit`, or use
**Terminate** in the console.

Everything in `/opt/taxify` is owned by `ubuntu`, and `/etc/taxify/taxify.env` is `root:ubuntu`.
As `ssm-user` you must either `sudo su - ubuntu` or prefix commands with `sudo`.

### Quick orientation

```sh
whoami                                   # ssm-user unless you switched
pwd
cd /opt/taxify && ls

sudo systemctl status taxify
sudo journalctl -u taxify -n 50 --no-pager

sqlite3 /opt/taxify/app.db "select id, email from user;"
sqlite3 /opt/taxify/app.db \
  "select id, status, job_type, substr(error_message,1,80) from automation_job order by id desc limit 5;"

sudo cat /etc/taxify/taxify.env          # 640 root:ubuntu, needs sudo
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/docs
```

### SSM gotchas

**The two SSM paths run as different users — don't confuse them:**

| Path | Runs as | Landing dir |
|---|---|---|
| `start-session` (Options A/B — interactive) | `ssm-user` | `/home/ssm-user` |
| `send-command` (Option C — scripted) | **`root`** | unset |

- **`send-command` runs as root.** Use `sudo -u ubuntu ...` for anything touching
  `/opt/taxify` ownership or the venv, or you will create root-owned files the service
  cannot write. (This is exactly how the `/home/ubuntu/.local` breakage happened during
  setup — see the gotchas table at the end.)
- **`send-command` has no `HOME`.** `git config --global` fails with `fatal: $HOME not set` —
  use `export HOME=/root`, or `git config --system`.
- git refuses the `ubuntu`-owned repo when running as root ("dubious ownership").
  Already fixed permanently with `git config --system --add safe.directory /opt/taxify`.
- **Output is truncated** by `send-command`. For long output, redirect to a file on the box and
  fetch it in pieces, or use an interactive session instead.

### Re-enabling SSH (emergency only)

The key pair and `sshd` still exist; only the firewall rule was removed.

```powershell
$MYIP = (curl.exe -s https://checkip.amazonaws.com).Trim()
aws ec2 authorize-security-group-ingress --profile myuser --region ap-south-1 `
  --group-id sg-01bac042739216d64 --protocol tcp --port 22 --cidr "$MYIP/32"
ssh -i ~/.ssh/taxify-key.pem ubuntu@43.205.225.117
# revoke it again afterwards
```

Expect it to fail intermittently under CGNAT. Prefer SSM.

---

## Service control

```bash
sudo systemctl status  taxify     # state
sudo systemctl restart taxify     # after config/env/code change
sudo systemctl stop    taxify
sudo systemctl start   taxify
systemctl is-active taxify nginx  # quick health
```

Both `taxify` and `nginx` are `enabled`, so they start automatically on boot.
**Verified by a real reboot** — no manual intervention needed.

---

## Logs

```bash
sudo journalctl -u taxify -f              # live tail
sudo journalctl -u taxify -n 100          # last 100 lines
sudo journalctl -u taxify -b              # since this boot
sudo journalctl -u taxify -p err          # errors only
sudo journalctl -u taxify --since "1 hour ago"

sudo tail -f /var/log/nginx/access.log    # HTTP traffic
sudo tail -f /var/log/nginx/error.log
```

Automation job failures are also recorded in the database:

```bash
sqlite3 /opt/taxify/app.db \
  "select id, status, job_type, error_message from automation_job order by id desc limit 10;"
```

---

## Redeploy after a code change

```bash
cd /opt/taxify
git fetch --all && git reset --hard origin/main     # NOTE: origin/main, not master
./.venv/bin/pip install -r requirements.txt          # only if requirements changed
sudo systemctl restart taxify
```

Frontend changes also need a rebuild:

```bash
cd /opt/taxify/frontend
NODE_OPTIONS=--max-old-space-size=1536 npm run build
# no restart needed — nginx serves dist/ from disk
```

> **The repo default branch is `master`, which is a stale line of work.** Always use `main`.
> A bare `git clone` or `git pull` without specifying the branch will get the wrong code.

> Building on the box uses swap and takes a few minutes on 914 MB RAM. Roadmap §10 moves this
> to GitHub Actions, which removes the build from the box entirely.

---

## Environment variables and secrets

```bash
sudo nano /etc/taxify/taxify.env     # the real file
sudo systemctl restart taxify        # required — changes are read only at startup
```

- Mode `640`, owner `root:ubuntu`. **Do not make it `600`** — the app calls `load_dotenv()` as
  `ubuntu` at `app/main.py:19` and will crash with `PermissionError` on startup.
- `/opt/taxify/.env` is a symlink to it.
- The app writes `/opt/taxify/.env.backup` on every start (`app/security/env_backup.py`).
- Never commit it. `.env` is gitignored.

### Switching to ERI production (when ITD issues credentials)

Currently Type-3 **UAT**. Production keys are deliberately empty. To go live, set all three:

```
ERI_SW_ID_TYPE3_PRODUCTION=...
ERI_DIGEST_SECRET_KEY_TYPE3_PRODUCTION=...
ERI_USER_ID_TYPE3_PRODUCTION=...
ERI_ENV=production
```

then `sudo systemctl restart taxify`.

**All three are mandatory.** With any missing, startup fails:
`config.py:151` raises `ValueError` on a missing SW_ID, and `assert_credentials_at_startup()`
raises on a missing digest secret. The SW_ID and digest secret must come from the *same*
`(mode, environment)` suffix or ITD will reject the JSON.

---

## TLS

Auto-renews via `certbot.timer`. Nothing to do normally.

```bash
sudo certbot certificates          # expiry
sudo certbot renew --dry-run       # prove renewal works
systemctl is-active certbot.timer
```

Certificate covers `itrbharo.duckdns.org` **and** `www.itrbharo.duckdns.org`, expires
**2026-11-22**.

If you ever replace `/etc/nginx/sites-available/taxify`, certbot's TLS block is overwritten —
re-apply it:

```bash
sudo certbot install --cert-name itrbharo.duckdns.org --nginx --redirect
```

---

## nginx routing — read before editing

`/clients` and `/dashboard` exist as **both** an SPA route and an API route, so path matching
alone cannot separate them. The config dispatches on the `Accept` header instead: browser
navigations (`text/html`) get `index.html`; everything else is proxied to uvicorn.

```bash
sudo nano /etc/nginx/sites-available/taxify
sudo nginx -t && sudo systemctl reload nginx
```

Sanity-check both directions after any change:

```bash
curl -s -o /dev/null -w '%{http_code} %{size_download}\n' \
  -H 'Accept: application/json' https://itrbharo.duckdns.org/dashboard/stats   # expect 401 62
curl -s -o /dev/null -w '%{http_code} %{size_download}\n' \
  -H 'Accept: text/html' https://itrbharo.duckdns.org/filing/x/2026-27          # expect 200 542
```

**542 bytes is `index.html`.** An API route returning 542 bytes means HTML is leaking through
and the routing is broken.

---

## Google Search Console verification — do not delete

`https://itrbharo.duckdns.org/googleb4679a5f656c872a.html` must keep returning **200** or the
Search Console property silently loses verification.

```
file    : /var/www/verification/googleb4679a5f656c872a.html   (root:root, 644)
nginx   : location = /googleb4679a5f656c872a.html  ->  root /var/www/verification
in git  : NO - ignored via google*.html in .gitignore
```

**It lives outside `frontend/dist` on purpose.** `deploy.sh` replaces `dist/` wholesale on every
release, so a copy placed there would be destroyed by the next deploy and un-verify the
property. Serving it from `/var/www/verification` means deploys cannot touch it — verified by
running a full deploy and re-checking.

Check it after any nginx change:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://itrbharo.duckdns.org/googleb4679a5f656c872a.html
```

If it ever 404s, recreate it (the token is the filename itself):

```bash
sudo mkdir -p /var/www/verification
printf '\ngoogle-site-verification: googleb4679a5f656c872a.html\n' | \
  sudo tee /var/www/verification/googleb4679a5f656c872a.html
sudo chmod 644 /var/www/verification/googleb4679a5f656c872a.html
```

Adding a second search engine later (Bing, Yandex) follows the same pattern — drop the token
file in that directory and add a matching `location =` block.

## Health checks

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/docs          # on the box
curl -s -o /dev/null -w '%{http_code}\n' https://itrbharo.duckdns.org/health # public
free -h                                                                       # swap in use?
df -h /                                                                       # disk
systemctl show taxify -p MemoryCurrent -p MemoryMax                          # cgroup memory
```

---

## Resource limits — this is a 914 MB box

The unit caps memory at `MemoryMax=750M` / `MemoryHigh=650M` with
`KillMode=control-group`. Without the cap the kernel OOM-killer picks uvicorn (largest RSS)
rather than a leaked Chrome, taking the whole API down.

Steady state is ~130–240 MB. If it sits near 750 M, look for leaked Chrome processes:

```bash
pgrep -af chrome | head
pkill -f "chrome.*--headless"     # a cron job does this every 30 min for procs older than 2h
```

`--workers 1` is **required**: `browser.py` holds a singleton browser that is not safe across
worker processes. Do not raise it.

---

## Database

SQLite at `/opt/taxify/app.db`, WAL mode.

```bash
sqlite3 /opt/taxify/app.db "select id, email from user;"
sqlite3 /opt/taxify/app.db "PRAGMA journal_mode;"      # expect: wal
sqlite3 /opt/taxify/app.db "PRAGMA integrity_check;"   # expect: ok
```

Back up (safe while running — never just `cp` a live WAL database):

```bash
sqlite3 /opt/taxify/app.db ".backup '/home/ubuntu/app.db.bak'"
```

Then pull it down:

```bash
scp -i ~/.ssh/taxify-key.pem ubuntu@43.205.225.117:/home/ubuntu/app.db.bak ./
```

---

## Cost guard — keep it $0

| Rule | Why |
|---|---|
| **Never launch a second instance** | 750 free hrs/month is account-wide; two instances split it and then bill |
| **Never change the instance type** | Only `t2.micro`/`t3.micro` are free. `t3.small` is not |
| **Never set `CpuCredits=unlimited`** | T3 default bills surplus CPU credits. Must stay `standard` |
| **Never release the EIP while the instance lives** | An unattached Elastic IP bills immediately |
| **Keep total EBS ≤ 30 GB** | Currently 16 GB |
| **Take no EBS snapshots** | Only 1 GB free |
| **Create no CloudWatch alarms** | Budgets are free; alarms beyond the default 10 are not |

Spot-check anytime:

```powershell
aws ec2 describe-instances --profile myuser --region ap-south-1 `
  --filters "Name=instance-state-name,Values=running" `
  --query 'Reservations[].Instances[].[InstanceId,InstanceType]' --output text
aws ec2 describe-instance-credit-specifications --profile myuser --region ap-south-1 `
  --instance-ids i-06fa754bdb98c95af --query 'InstanceCreditSpecifications[0].CpuCredits' --output text
```

⚠️ **Free tier expires ~2027-08-24.** After that the public IPv4 alone costs ~$3.60/month and
is unavoidable while the box is reachable. Set a reminder for ~2027-07.

---

## Known gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `ls` shows nothing after connecting | You're in `/home/ssm-user`, which is empty | `cd /opt/taxify` |
| `sh: cd: can't cd to taxify` | Relative path; you aren't in `/opt` | `cd /opt/taxify` (absolute) |
| Permission denied on app files | You're `ssm-user`, not `ubuntu` | `sudo su - ubuntu` |
| No tab-completion / history | Session shell is `dash`, not bash | run `bash` |
| `Ctrl-C` won't exit the session | It only interrupts the command | type `exit` |
| SSH times out | Your ISP IP rotated (CGNAT) | Use SSM instead — see top of this doc |
| API returns HTML (542 bytes) | nginx routing regression | See "nginx routing" above |
| SPA deep link 404s | Same | Same |
| `PermissionError: /opt/taxify/.env` on startup | Env file set back to `600` | `chmod 640`, `chown root:ubuntu` |
| `PermissionError: /home/ubuntu/.local/...` in a job | Root-owned dirs from a `sudo -E` install | `sudo chown -R ubuntu:ubuntu /home/ubuntu/.local` |
| Job fails: "missing PAN or ITD portal password" | Client data, not infra | Set `portal_password` on the client |
| Deployed the wrong code | Cloned default branch `master` | Use `main` |
| Frontend build OOMs | 914 MB RAM | Confirm swap is on; cap heap at 1536 MB |

---
