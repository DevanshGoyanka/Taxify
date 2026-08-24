# Taxify AWS Resource Inventory

Every AWS resource **actually created** for Taxify. Updated immediately after each is provisioned.

| | |
|---|---|
| **Account** | `938509046486` |
| **Identity** | `arn:aws:iam::938509046486:user/itr` |
| **CLI profile** | `myuser` |
| **Region** | `ap-south-1` (Mumbai) |
| **Free tier window** | account created 2026-08-24 → expires **~2027-08-24** |

Roadmap ledger: `Docs/AWS_FREE_TIER_DEPLOYMENT.md` §3

---

## Created for Taxify

| # | Resource ID | Type | Region | Ledger line | Free tier limit | Usage | Created |
|---|---|---|---|---|---|---|---|
| 1 | `key-0776e287e2c399152` (`taxify-key`) | EC2 key pair | ap-south-1 | §3.8 | Always free | 1 | 2026-08-24 21:14 |
| 2 | `sg-01bac042739216d64` (`taxify-sg`) | Security group | ap-south-1 | §3.7 | Always free | 1 | 2026-08-24 |
| 3 | `i-06fa754bdb98c95af` (`taxify`) | EC2 **t3.micro**, `CpuCredits=standard` | ap-south-1c | §3.1 | 750 hrs/mo, 12 mo | 744 hrs | 2026-08-24 |
| 4 | `vol-0ed5c1f4e9dd78914` | EBS **16 GiB gp3**, 3000 IOPS | ap-south-1c | §3.2 | 30 GB, 12 mo | 16 GB | 2026-08-24 |
| 5 | `eipalloc-03d23487a47ffde51` → **`43.205.225.117`** | Elastic IP (attached) | ap-south-1 | §3.3 | 750 hrs/mo, 12 mo | 744 hrs | 2026-08-24 |
| 6 | `taxify-zero` | AWS Budget, $1 / monthly | global | §4.8 | 2 budgets free | 1 | 2026-08-24 |

**Count: 6 — all inside the §3 ledger. Projected monthly cost: $0.00**

### Key details

- **Public IP:** `43.205.225.117` ← `itrbharo.duckdns.org` must point here
- **EIP association:** `eipassoc-03768b8c3b44ba343` — **attached**, so §4.2 (idle-EIP billing) does not apply
- **Instance private IP:** `172.31.27.231` · AMI `ami-0aa761682283b4cc8` (Ubuntu 22.04.5 LTS)
- **Verified on box:** 2 vCPU, **914 MB RAM**, 16 G root with 14 G free
- **Budget alert email:** `sidworkcode18@gmail.com`
- **Private key:** `C:\Users\LENOVO\.ssh\taxify-key.pem`
  ACL locked to `SIDDHESH-LOQ\LENOVO:(R)` via `icacls` — Git Bash `chmod 400` does not set real
  Windows ACLs and OpenSSH refuses a world-readable key.
  Fingerprint `97:6d:65:4e:10:e3:b9:83:d1:d7:23:4b:54:c6:63:1a:87:4a:04:f6`

### DNS (not an AWS resource — free, Route 53 excluded by §3)

| Hostname | A record | Verified |
|---|---|---|
| `itrbharo.duckdns.org` | `43.205.225.117` | ✅ 2026-08-24, incl. via resolver `1.1.1.1` |
| `www.itrbharo.duckdns.org` | `43.205.225.117` | ✅ DuckDNS wildcard |

No DuckDNS updater daemon is needed — the Elastic IP is static, so the record never changes.
The DuckDNS token is **not** stored on the box or in this repo.

### Security group rules (`sg-01bac042739216d64`)

| Port | Source | Purpose |
|---|---|---|
| 22 | `106.221.215.87/32` | SSH — **your IP only** (dynamic; re-authorise when it rotates) |
| 80 | `0.0.0.0/0` | nginx HTTP + Let's Encrypt HTTP-01 challenge |
| 443 | `0.0.0.0/0` | nginx HTTPS |
| 8000 | *not exposed* | uvicorn stays on localhost behind nginx |

---

## Pre-existing defaults used (NOT created by this deployment)

These ship with every AWS account. Read-only lookups in §5.2 — nothing was created or modified.

| Resource ID | Type | Region | Ledger line | Note |
|---|---|---|---|---|
| `vpc-0d38055941d285070` | Default VPC | ap-south-1 | §3.7 always free | — |
| `subnet-0decad573b3a94e85` | Default subnet | ap-south-1 (`ap-south-1c`) | §3.7 always free | `172.31.16.0/20`, auto-assign public IP = **True** |
| `igw-06c9071ee9b7f3df0` | Internet Gateway | ap-south-1 | §3.7 always free | Public subnet path — **no NAT Gateway** (§3 excluded) |
| `sg-0496eb12236cd7128` | Default security group | ap-south-1 | §3.7 always free | Not used; Taxify gets its own SG |

---

## Free tier headroom

Account is new and empty — the full allowance is available to Taxify.

| Ledger line | Limit | Used by others | Taxify needs | Verdict |
|---|---|---|---|---|
| §3.1 EC2 micro hours | 750 hrs/mo | 0 | 744 | ✅ fits |
| §3.2 EBS gp3 | 30 GB | 0 | 16 GB | ✅ fits |
| §3.3 Public IPv4 | 750 hrs/mo | 0 | 744 | ✅ fits |
| §3.4 Data transfer out | 100 GB/mo | 0 | low | ✅ fits |
| §3.5 EBS snapshots | 1 GB | 0 | 0 (take none) | ✅ skip |
| §3.6 CloudWatch | 10 alarms | 0 | 0 | ✅ fits |
| §3.7 VPC/Subnet/IGW/SG | Always free | — | 1 SG | ✅ free |
| §3.8 Key pair | Always free | — | 1 | ✅ free |

### Confirmed absent account-wide (the expensive ones)

| Resource | Scope checked | Result |
|---|---|---|
| EC2 instances | **all regions** | ✅ none |
| Elastic IPs | **all regions** | ✅ none |
| RDS | ap-south-1 | ✅ none |
| Load balancers (ALB/ELB) | ap-south-1 | ✅ none |
| NAT gateways | ap-south-1 | ✅ none |
| EBS volumes | ap-south-1 | ✅ none |

**On-Demand Standard vCPU quota: 5.0** — sufficient for t3.micro (2 vCPU).

---
