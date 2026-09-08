# Security Policy

Taxify processes **real taxpayer PII** (PAN, Aadhaar-linked data, income details, bank
accounts) and holds **live ERI credentials** issued by the Income Tax Department. Treat every
security issue here as high severity by default.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security problem.**

Email **sidworkcode18@gmail.com** with:

- what the issue is and where (file/endpoint)
- steps to reproduce
- what an attacker could achieve
- any suggested fix

Expect an acknowledgement within 72 hours.

## Handling secrets

Never commit these. `.gitignore` covers them; verify before every push.

| Secret | Where it belongs |
|---|---|
| ERI credentials (`ERI_*`) | `.env` locally · `/etc/taxify/taxify.env` on the server |
| `SECRET_KEY` (JWT signing) | same |
| `PORTAL_ENCRYPTION_KEY` (encrypts stored ITD portal passwords) | same |
| DSC certificates / keystores (`*.pfx`, `*.p12`, `*.jks`, `*.pem`) | never in the repo |
| `app.db` | never in the repo — it contains client PII |

On the server the env file is `640 root:ubuntu` — readable by the service account only.
It must **not** be `600`: the app calls `load_dotenv()` as `ubuntu` and will fail to start.

If a secret is ever committed, rotating it is mandatory — git history preserves it even after
the file is deleted.

### Rotating

- `SECRET_KEY` — safe to rotate any time. Invalidates existing JWTs; users re-login.
- `PORTAL_ENCRYPTION_KEY` — **destructive.** Invalidates every stored portal password.
  Use `scripts/regen_portal_key.py` and `scripts/clear_broken_portal_passwords.py`.
- ERI credentials — reissued by ITD; must match the active `(ERI_MODE, ERI_ENV)` suffix.

## Deployment security posture

| Control | State |
|---|---|
| SSH (port 22) | **Closed to the internet.** Access via AWS SSM, outbound only |
| HTTPS | Let's Encrypt, auto-renewing, HTTP redirects to HTTPS |
| API port 8000 | Bound to `127.0.0.1` only, never exposed |
| Database | SQLite on local disk, not network-accessible |
| Secrets at rest | `640 root:ubuntu`, outside the repo tree |
| AWS access | IAM user, not root; per-person users, no shared credentials |

## Reporting scope

In scope: authentication/authorisation flaws, PII exposure, secret leakage, injection,
SSRF, insecure deserialisation, dependency vulnerabilities with a practical exploit path.

Out of scope: findings that require an already-compromised host, missing hardening headers
with no demonstrated impact, and automated scanner output without a working proof of concept.

## Known accepted risks

- **ERI Type-2 DSC signing is Windows-only** (`win32crypt`). Unavailable on the Linux host;
  the deployment runs Type-3, which needs no DSC.
- **SQLite, single node.** No replication. Back it up (`runbook.md`) before risky changes.
- **`--workers 1` is mandatory** — `browser.py` holds a singleton Playwright browser that is
  not safe across worker processes.
