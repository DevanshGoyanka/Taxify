# Taxify AWS Teardown — copy-paste ready

Roadmap §9, with the **actual resource IDs** from `docs/resource-inventory.md` substituted.
Run top to bottom. Order matters: the Elastic IP must be released **after** the instance is
terminated, or it starts billing as an idle address.

| | |
|---|---|
| **Account** | `938509046486` |
| **Profile** | `myuser` — **required on every command** |
| **Region** | `ap-south-1` (Mumbai) |

---

## 9.1 Back up data FIRST — terminating destroys the EBS volume

```bash
scp -i ~/.ssh/taxify-key.pem ubuntu@43.205.225.117:/opt/taxify/app.db ./app.db.backup
scp -i ~/.ssh/taxify-key.pem -r ubuntu@43.205.225.117:/opt/taxify/downloads ./downloads.backup
```

## 9.2 Terminate the instance

```powershell
aws ec2 terminate-instances --profile myuser --region ap-south-1 --instance-ids i-06fa754bdb98c95af
aws ec2 wait instance-terminated --profile myuser --region ap-south-1 --instance-ids i-06fa754bdb98c95af
```

`vol-0ed5c1f4e9dd78914` has `DeleteOnTermination=true`, so it is destroyed automatically.
Step 9.6 verifies no orphan survived.

## 9.3 RELEASE the Elastic IP — the #1 forgotten charge (§4.2)

```powershell
aws ec2 release-address --profile myuser --region ap-south-1 --allocation-id eipalloc-03d23487a47ffde51
```

## 9.4 Delete the security group (only after the instance is fully terminated)

```powershell
aws ec2 delete-security-group --profile myuser --region ap-south-1 --group-id sg-01bac042739216d64
```

## 9.5 Delete the key pair

```powershell
aws ec2 delete-key-pair --profile myuser --region ap-south-1 --key-name taxify-key
Remove-Item "$env:USERPROFILE\.ssh\taxify-key.pem"
```

## 9.5b CI/CD IAM objects (§10)

Only if §10 was set up. Harmless no-ops otherwise.

```powershell
aws iam remove-role-from-instance-profile --profile myuser --instance-profile-name taxify-ssm --role-name taxify-ssm
aws iam delete-instance-profile --profile myuser --instance-profile-name taxify-ssm
aws iam detach-role-policy --profile myuser --role-name taxify-ssm --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam delete-role --profile myuser --role-name taxify-ssm
aws iam delete-role --profile myuser --role-name taxify-gha-deploy
```

## 9.6 Confirm NOTHING remains

```powershell
# expect empty
aws ec2 describe-instances --profile myuser --region ap-south-1 --filters "Name=instance-state-name,Values=running,stopped" --query 'Reservations[].Instances[].InstanceId' --output text
# expect empty
aws ec2 describe-addresses --profile myuser --region ap-south-1 --query 'Addresses[]' --output text
# expect empty — orphaned volumes bill
aws ec2 describe-volumes --profile myuser --region ap-south-1 --filters Name=status,Values=available --query 'Volumes[].VolumeId' --output text
# expect empty
aws ec2 describe-snapshots --profile myuser --region ap-south-1 --owner-ids self --query 'Snapshots[].SnapshotId' --output text
```

## 9.7 Check EVERY region — orphans hide where you forgot

```powershell
foreach ($r in (aws ec2 describe-regions --profile myuser --region ap-south-1 --query 'Regions[].RegionName' --output text).Split()) {
  $i = aws ec2 describe-instances --profile myuser --region $r --filters "Name=instance-state-name,Values=running,stopped" --query 'Reservations[].Instances[].InstanceId' --output text
  $e = aws ec2 describe-addresses --profile myuser --region $r --query 'Addresses[].PublicIp' --output text
  if ($i) { Write-Output "!! INSTANCE $r : $i" }
  if ($e) { Write-Output "!! EIP      $r : $e" }
}
Write-Output "no '!!' lines = account is clean"
```

## 9.8 Delete the budget

```powershell
aws budgets delete-budget --profile myuser --account-id 938509046486 --budget-name taxify-zero
```

## 9.9 DuckDNS

Delete or re-point `itrbharo.duckdns.org` at duckdns.org. Free either way.

## 9.10 Disable CI/CD

Delete `.github/workflows/deploy.yml` or disable it in the repo's Actions tab, so pushes stop
firing against a dead instance.

## 9.11 Final billing confirmation

Check **Billing → Bills** 24–48 h later. Month-to-date must read **$0.00**.

---

## Resource checklist

| # | Resource ID | Deleted by step |
|---|---|---|
| 1 | `i-06fa754bdb98c95af` (t3.micro) | 9.2 |
| 2 | `vol-0ed5c1f4e9dd78914` (16 GiB gp3) | 9.2 (auto, DeleteOnTermination) |
| 3 | `eipalloc-03d23487a47ffde51` (`43.205.225.117`) | 9.3 |
| 4 | `sg-01bac042739216d64` (taxify-sg) | 9.4 |
| 5 | `key-0776e287e2c399152` (taxify-key) | 9.5 |
| 6 | `taxify-zero` (budget) | 9.8 |

**Not created by this deployment — do not delete:** `vpc-0d38055941d285070`,
`subnet-0decad573b3a94e85`, `igw-06c9071ee9b7f3df0`, `sg-0496eb12236cd7128` (default SG).
These are AWS account defaults and are always free.

---
