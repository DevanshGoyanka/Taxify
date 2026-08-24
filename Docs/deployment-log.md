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

## Phase 2 — §6 Box setup

_(not started — awaiting go-ahead)_

---
