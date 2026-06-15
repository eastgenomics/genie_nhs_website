# NHS GENIE: Deployment and Testing Guide

## Table of Contents

- [How It All Fits Together](#how-it-all-fits-together)
- [Prerequisites](#prerequisites)
- [Infrastructure Setup](#infrastructure-setup)
- [Deploying the Application](#deploying-the-application)
- [Updating GENIE Data](#updating-genie-data)
- [Acceptance Testing](#acceptance-testing)
- [Full Data Update Workflow](#full-data-update-workflow)
- [SSL Certificate Setup](#ssl-certificate-setup)
- [Troubleshooting](#troubleshooting)
- [Makefile Reference](#makefile-reference)

---

## How It All Fits Together

If you're new to infrastructure as code (IaC) and Terraform, this section explains how the
different pieces relate to each other before diving into the details.

### What is infrastructure as code?

Traditionally, setting up a server means clicking through the AWS console — creating an EC2
instance, configuring security groups, setting up DNS, etc. Infrastructure as code replaces
this with configuration files that describe the desired state. You run a single command and
the tool (Terraform) creates or updates everything to match.

**Benefits:** Repeatable (spin up identical UAT/prod environments), version-controlled
(changes are tracked in Git), reviewable (PRs for infrastructure changes), and disposable
(tear down and recreate at will).

### Architecture overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Your local machine                           │
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────────┐  │
│  │ Makefile  │───>│   Terraform  │───>│  AWS (genie-website acct) │  │
│  │           │    │  terraform/  │    │                           │  │
│  │ make ...  │    │  *.tf files  │    │  EC2, IAM, Route53, etc.  │  │
│  └─────┬─────┘   └──────────────┘    └─────────────┬─────────────┘  │
│        │                                            │                │
│        │         ┌──────────────┐                   │                │
│        └────────>│   Scripts    │──── SSH ──────────>│                │
│                  │  deploy.sh   │                    │                │
│                  │  update_data │              ┌─────┴──────┐        │
│                  └──────────────┘              │ EC2 Server │        │
│                                               │            │        │
│  ┌──────────────────┐                         │  Docker     │        │
│  │ acceptance_test.py│──── HTTP ──────────────>│  ├ Django   │        │
│  │ (runs locally)    │                        │  ├ Gunicorn │        │
│  └──────────────────┘                         │  └ SQLite   │        │
│                                               │            │        │
│                                               │  Nginx ─┐  │        │
│                                               │  (host) │  │        │
│                                               └─────────┘  │        │
│                                    https://genie.genomics- │        │
│                                    resources.uk ───────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

### Key components and what they do

| Component | Location | Purpose |
|---|---|---|
| **Terraform files** (`terraform/*.tf`) | Repo | Describe the AWS infrastructure — what to create and how to configure it |
| **Terraform state** (S3 bucket) | AWS | Tracks what Terraform has created so it knows what to update or delete |
| **Terraform workspaces** | Terraform | Separate state for each environment (prod, uat, beta) using the same `.tf` files |
| **user_data.sh** | `terraform/` | Bootstrap script that runs once when a new EC2 instance starts — installs Docker, Nginx (with GeoIP2 UK geo-restriction), clones the repo |
| **Makefile** | Repo root | Single entry point for all operations — wraps Terraform and SSH commands |
| **deploy.sh** | `scripts/` | SSHes to the server, pulls latest code, rebuilds Docker |
| **update_data.sh** | `scripts/` | SSHes to the server, downloads VCF from S3, re-imports the database |
| **acceptance_test.py** | `scripts/` | Runs from your machine, makes HTTP requests to the website, checks responses |
| **SSM Parameter Store** | AWS | Stores the `.env` file securely — pulled by `user_data.sh` during bootstrap |

### How environments work

Terraform workspaces let you use the same configuration files to create separate,
independent environments. Each workspace has its own state (what resources exist) and
its own DNS name:

```
terraform/                         AWS
  *.tf files  ─── workspace "prod" ──> genie.genomics-resources.uk     (t3.large, 30GB, EIP, alarms)
              ─── workspace "uat"  ──> uat.genie.genomics-resources.uk  (t3.medium, 20GB, no alarms)
              ─── workspace "beta" ──> beta.genie.genomics-resources.uk (t3.medium, 20GB, no alarms)
```

Non-prod environments are designed to be short-lived — spin up for testing, tear down when done.

### Typical workflow at a glance

```
You type:                          What happens:
─────────                          ──────────────
make tf-init                       Downloads Terraform providers, connects to state bucket
make uat-up                        Creates EC2 + security group + DNS + IAM role for UAT
make update-data ENV=uat VCF=...   SSHes in, downloads VCF from S3, imports into SQLite
make verify-db ENV=uat             SSHes in, queries SQLite row counts
make acceptance-test               Runs Python test script against the website over HTTP
make uat-down ENV=uat              Destroys all UAT resources (EC2, DNS record, etc.)
```

The rest of this document covers each step in detail.

---

## Prerequisites

### One-time AWS setup (manual)

These resources must exist before Terraform can be initialised:

1. **S3 bucket for Terraform state** - Create with versioning enabled. Name must match the `bucket` field in `terraform/main.tf` (`804761969039-genie-terraform-state`).

2. **DynamoDB table for state locking** - Create with `LockID` as the partition key (string). Name must match `dynamodb_table` in `terraform/main.tf` (default: `terraform-locks`).

3. **SSM Parameter Store entries** - Store the `.env` file contents as `SecureString` parameters:
   - `/genie/prod/env` - production environment variables
   - `/genie/uat/env` - UAT environment variables

   Each parameter should contain the full `.env` file content, e.g.:
   ```ini
   DEBUG=0
   SECRET_KEY=<random-secret>
   USE_WHITENOISE=1
   PORT=8000
   ALLOWED_HOSTS=genie.genomics-resources.uk,uat.genie.genomics-resources.uk
   DB_NAME=db.sqlite3
   GENIE_VERSION=v19
   GENIE_VCF=GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz
   GENIE_CANCER_TYPES_CSV=GENIE_v19_cancer_types.csv
   GOOGLE_ANALYTICS_ID=<GA4-measurement-id>
   ```

   See `README.md` for the full list of supported environment variables.

   **Note:** SSM is used for initial instance provisioning only. Once the instance is running, the data-related variables (`GENIE_VCF`, `GENIE_CANCER_TYPES_CSV`, `GENIE_VERSION`) are managed by `make update-data`, which modifies `.env` in-place on the instance. If the instance is ever re-provisioned from scratch, SSM provides the baseline `.env` again.

4. **EC2 key pair** - Confirm that the `nhs-genie` key pair exists in `eu-west-2`. The private key file must be available locally for SSH access.

5. **MaxMind GeoLite2 licence key (for UK geo-restriction)** - Store the MaxMind
   GeoLite2 licence key as an SSM `SecureString` parameter at
   `/genie/maxmind/license_key`. The instance uses it during bootstrap (and via
   a weekly cron) to download the `GeoLite2-Country` database that Nginx uses to
   restrict access to the UK and Crown Dependencies. This is only needed when
   `restrict_to_uk = true` (the default). To create it:
   ```bash
   aws ssm put-parameter --name /genie/maxmind/license_key \
     --type SecureString --value "<your-maxmind-licence-key>" --region eu-west-2
   ```

5. **S3 bucket for GENIE data** - The VCF and cancer types CSV must be uploaded to an S3 bucket. The EC2 instance role is granted read access to this bucket.

### Local machine requirements

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.5
- [AWS CLI](https://aws.amazon.com/cli/) configured with appropriate credentials
- SSH access to EC2 instances (key pair file)
- Python 3.8+ (for running acceptance tests)
- GNU Make

### SSH configuration

The Makefile connects via `ssh ubuntu@<ip>`. For this to work, configure your SSH client to use the correct key pair. Add to `~/.ssh/config`:

```
Host *.eu-west-2.compute.amazonaws.com
  User ubuntu
  IdentityFile ~/.ssh/nhs-genie.pem
```

Or for a specific IP:

```
Host nhs-genie
  HostName <elastic-ip>
  User ubuntu
  IdentityFile ~/.ssh/nhs-genie.pem
```

### Terraform variables

Edit `terraform/terraform.tfvars` with actual values before running Terraform:

```hcl
# The Ubuntu 24.04 LTS AMI is looked up automatically (data.aws_ami.ubuntu),
# so no ami_id is required.
key_pair_name   = "nhs-genie"
domain          = "genie.genomics-resources.uk"
route53_zone_id = "Z09949371PEDMO2FEKH29"   # Hosted zone for var.domain
s3_data_bucket  = "genie-website-data"      # S3 bucket with VCF/CSV
alert_email     = "your-team-inbox@nhs.net"         # CloudWatch alarm recipient
ssh_cidr_blocks = ["203.0.113.0/24"]         # Restrict SSH to your network

# UK geo-restriction (Nginx GeoIP2). Set restrict_to_uk = false to disable.
restrict_to_uk    = true
allowed_countries = ["GB", "IM", "JE", "GG"]
```

**Important:** `ssh_cidr_blocks` has no default value and must be set explicitly. A `terraform plan` will fail without it.

---

## Infrastructure Setup

### Initialise Terraform

```bash
make tf-init
```

### Create Terraform workspaces

Workspaces separate prod and UAT state. The `prod` workspace must be created manually:

```bash
cd terraform
terraform workspace new prod
cd ..
```

The `uat` workspace is created automatically by `make uat-up` if it doesn't exist.

### Provision production infrastructure

```bash
make tf-apply ENV=prod
```

This creates:
- EC2 instance (t3.large, 30 GB encrypted EBS, IMDSv2 enforced)
- Security group (SSH restricted to `ssh_cidr_blocks`, HTTP/HTTPS open)
- Elastic IP (prod only)
- IAM role with S3, SSM, and CloudWatch permissions
- Route53 A record (`genie.genomics-resources.uk` for prod; `uat.genie.genomics-resources.uk` for uat)
- CloudWatch alarms for CPU >80% and disk >80% (prod only)
- SNS topic with email subscription for alarm notifications

The EC2 user data script automatically installs Docker, Nginx (with the GeoIP2 UK geo-restriction), CloudWatch agent, clones the repo, pulls `.env` from SSM, runs migrations, and starts the application. **It does not load the GENIE data** — the database is empty until you run `make update-data` (see below).

**After the first `terraform apply`:** Check your email and click the SNS subscription confirmation link to enable alarm notifications.

To discover the instance IP after provisioning:

```bash
cd terraform && TF_WORKSPACE=prod terraform output public_ip
```

### Review planned changes

```bash
make tf-plan ENV=prod
```

### Destroy infrastructure

```bash
make tf-destroy ENV=prod
```

---

## Deploying the Application

To deploy the latest code to a running instance:

```bash
ssh-add ~/.ssh/nhs-genie.pem   # ensure key is in agent first
make deploy ENV=prod
```

This SSHes to the instance and runs:
1. `git pull origin main`
2. `docker system prune -a --force` (cleans old images to prevent disk exhaustion)
3. `docker compose up --build -d`
4. Waits up to 150 seconds for the container health check to pass

---

## Updating GENIE Data

### Upload data to S3

Before updating, ensure the new VCF and cancer types CSV are in the S3 data bucket:

```bash
aws s3 cp GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz s3://genie-website-data/
aws s3 cp GENIE_v19_cancer_types.csv s3://genie-website-data/
```

### Run the data update

```bash
make update-data ENV=prod \
  VCF=s3://genie-website-data/GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz \
  CSV=s3://genie-website-data/GENIE_v19_cancer_types.csv \
  VER=v19
```

This SSHes to the instance and runs:
1. Verifies AWS credentials on the instance
2. Downloads the VCF and CSV from S3 to the `data/` directory
3. Updates `.env` with the new filenames and version
4. Stops the running containers (**downtime starts**)
5. Runs `db_importer.py` inside a fresh container to re-import the database
6. Starts the containers (**downtime ends**)

**Expected downtime:** ~3-10 minutes (the v19 import of ~1.27M variants takes ~3-4 minutes once the VCF is downloaded).

**If the import fails or is killed:** The database will be empty (tables are truncated before re-import). See [Import killed / empty database](#import-killed--empty-database-exit-137) in Troubleshooting — on the t3.large instance the import can be OOM-killed if it runs alongside the live web workers. Do not leave the application running with an incomplete import.

### Verify the database

```bash
make verify-db ENV=prod
```

This SSHes to the instance and queries the database row counts:

```text
variants: 1267112
cancer_types: 115
```

Check that these counts match the expected values for your data version. For `GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz`, the expected variant count is **1,267,112** (the final VCF variant count from v19 acceptance testing) and **115** cancer types.

---

## Acceptance Testing

### Automated tests

The acceptance test suite (`scripts/acceptance_test.py`) runs two types of tests:

#### Known-value tests

Tests against hardcoded expected values from GENIE v19 acceptance testing
(GRCh38 coordinates; worked examples taken from the v19 controlled-file test page):

| Test | Query | Expected |
|------|-------|----------|
| KV-S1–S3 | `GET /`, `/main/about/`, `/main/variants/?...SAMHD1` | HTTP 200 |
| KV-1 | SAMHD1 20:36935111 G>A (p.Arg143Cys) row | gene SAMHD1; SameNucleotideChange All=2, HaemOnc=2, Solid=0 |
| KV-2 | SAMHD1 20:36935111 SameAminoAcidChange | All=2, Haemonc=2, Mature B-Cell Neoplasms=1, Mature T and NK Neoplasms=1 |
| KV-3 | SAMHD1 20:36927220 G>A (p.Arg220Ter) SameOrDownstreamTruncatingPerAA | All=21, Haemonc=20, Mature B-Cell=15, Mature T and NK=4, Histiocytosis=1, UNKNOWN=2 |
| KV-4 | SAMHD1 20:36919495 (p.Met240del) NestedInframeDeletionsPerAA | All=1, Haemonc=1, Mature B-Cell Neoplasms=1 |
| KV-5 | Cohort denominators (cancer_n) | All Cancers=208523, Haemonc=18695, Mature B-Cell Neoplasms=7653 |

**Note:** These expected values are for `GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz`. If the data version changes, update the expected values in `scripts/acceptance_test.py`.

#### Parity tests (UAT vs prod)

Compares JSON responses from the UAT and prod instances for identical queries. Both databases **must be loaded from the same VCF** for these to pass.

| Test | Query |
|------|-------|
| PT-1 | BRAF gene - rows and total identical |
| PT-2 | SAMHD1 gene - rows and total identical |
| PT-3 | Variant 20:36935111 (SAMHD1 p.Arg143Cys) cancer type patient counts identical |
| PT-4 | IDH1 gene - rows and total identical |

**When to use each test type:**

- **Parity tests** validate that the infrastructure and data import pipeline produce identical results on a new instance. Use when loading the *same* VCF version as prod (e.g. after infrastructure changes or pipeline testing).
- **Known-value tests** validate correctness against documented expected values. Use for both same-version and new-version deployments. When deploying a new data version, update the expected values in `acceptance_test.py` first.

#### Running the tests

> **Important — which URL to use.** Instances are served by Nginx on ports 80/443
> only (the security group does **not** expose the app's port 8000), and Django
> enforces `ALLOWED_HOSTS`, which is set to the site's domain. So the tests must be
> pointed at the public site URL, **not** `http://<ip>:8000`. For prod that is
> `https://genie.genomics-resources.uk`; for uat, `https://uat.genie.genomics-resources.uk`
> (or `http://...` before its certificate is issued). Requests must also originate
> from an allowed country (see [UK Geo-restriction](#uk-geo-restriction)).

Run the known-value suite directly against the public URL (recommended):

```bash
python3 scripts/acceptance_test.py \
  --uat-url https://genie.genomics-resources.uk \
  --mode known-values
```

Run known-value + parity (UAT vs prod):

```bash
python3 scripts/acceptance_test.py \
  --uat-url https://uat.genie.genomics-resources.uk \
  --prod-url https://genie.genomics-resources.uk \
  --mode all
```

The script exits with code 0 if all tests pass, 1 if any fail.

> **Note on the `make acceptance-test*` targets.** These resolve the instance's
> public FQDN from the Terraform `fqdn` output and call `$(SCHEME)://<fqdn>`
> (`SCHEME` defaults to `https`). This goes through Nginx on 443/80 and satisfies
> the domain-based `ALLOWED_HOSTS`, so the targets work against the infrastructure
> created here. Before a certificate has been issued for a new environment, pass
> `SCHEME=http` (e.g. `make acceptance-test-known-values ENV=uat SCHEME=http`).
> Requests must also originate from an allowed country (see
> [UK Geo-restriction](#uk-geo-restriction)).

### Manual acceptance checklist

Print the checklist with UAT URL pre-filled:

```bash
make acceptance-checklist
```

Or with a custom prod URL:

```bash
make acceptance-checklist PROD_URL=https://genie.genomics-resources.uk
```

The checklist covers:
- **Navigation** - Homepage, About page, navbar links
- **Search** - Gene search, region search, range queries, invalid input handling
- **Variant table** - Column display, row expansion, consequence filters, silent-variant default, protein-position sorting/filtering
- **Geo-restriction** - 200 from a UK connection, 403 from a non-UK connection
- **Visual/UI** - CSS rendering, JS console errors, info modals, version string

---

## Full Data Update Workflow

The recommended workflow for deploying a new GENIE data release uses a UAT-first approach:

```
                                   ┌─────────────────────────┐
                                   │  New VCF + CSV in S3    │
                                   └────────────┬────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. make uat-up                                                 │
│     Provisions a short-lived UAT EC2 instance via Terraform     │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. make update-data ENV=uat VCF=s3://... CSV=s3://... VER=...  │
│     Downloads data, imports into database                       │
│     NOTE: app is not functional until this step completes       │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. make verify-db ENV=uat                                      │
│     Checks variant and cancer type row counts                   │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. make acceptance-test [PROD_URL=...]                          │
│     Known-value tests always run.                               │
│     Parity tests run only if PROD_URL is set and both           │
│     instances have the same data version.                       │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. make acceptance-checklist                                   │
│     Manual browser testing against UAT instance                 │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
                              [Manual sign-off]
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. make update-data ENV=prod VCF=s3://... CSV=s3://... VER=... │
│     Applies the same data to production (~2-10 min downtime)    │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. make acceptance-test-known-values ENV=prod                  │
│     Re-runs known-value tests against prod to confirm           │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  8. make uat-down ENV=uat                                       │
│     Tears down the UAT instance to save costs                   │
└─────────────────────────────────────────────────────────────────┘
```

### Example session

```bash
# 1. Spin up UAT
make uat-up

# 2. Load the new data (app is not functional until this completes)
make update-data ENV=uat \
  VCF=s3://genie-website-data/GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz \
  CSV=s3://genie-website-data/GENIE_v19_cancer_types.csv \
  VER=v19

# 3. Verify database
make verify-db ENV=uat

# 4. Run automated tests against the UAT site URL
#    (parity only if UAT and prod share the same VCF version)
python3 scripts/acceptance_test.py \
  --uat-url https://uat.genie.genomics-resources.uk --mode known-values

# 5. Manual testing
make acceptance-checklist

# 6. Promote to production
make update-data ENV=prod \
  VCF=s3://genie-website-data/GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz \
  CSV=s3://genie-website-data/GENIE_v19_cancer_types.csv \
  VER=v19

# 7. Verify production
python3 scripts/acceptance_test.py \
  --uat-url https://genie.genomics-resources.uk --mode known-values

# 8. Tear down UAT
make uat-down ENV=uat
```

---

## SSL Certificate Setup

After provisioning production infrastructure and waiting for DNS propagation (~1-2 minutes):

```bash
make ssl CERTBOT_EMAIL=your-email@example.com
```

This runs certbot with the Nginx plugin on the prod instance. Certbot installs a systemd timer that handles automatic certificate renewal.

Without an email (not recommended for production):

```bash
make ssl
```

---

## UK Geo-restriction

The site is restricted to the UK and Crown Dependencies using Nginx with the
[GeoIP2 module](https://github.com/leev/ngx_http_geoip2_module) and the MaxMind
`GeoLite2-Country` database. This is configured by `terraform/user_data.sh` at
bootstrap and controlled by two Terraform variables:

| Variable | Default | Purpose |
|---|---|---|
| `restrict_to_uk` | `true` | Enable/disable the geo-restriction |
| `allowed_countries` | `["GB", "IM", "JE", "GG"]` | ISO 3166-1 alpha-2 codes allowed (UK + Isle of Man, Jersey, Guernsey) |

**How it works:**
- `user_data.sh` installs `libnginx-mod-http-geoip2`, fetches the MaxMind licence
  key from SSM (`/genie/maxmind/license_key`), and downloads `GeoLite2-Country.mmdb`.
- An Nginx `map` sets `$allowed_country` from the resolved country code; requests
  from other countries receive **HTTP 403**.
- A weekly cron (`/etc/cron.d/update-geolite2`) refreshes the database and reloads Nginx.

**Notes / limitations:**
- GeoIP is best-effort (~99% country accuracy) and can be bypassed by VPNs; it is a
  jurisdictional control, not a security boundary.
- The MaxMind licence key must exist in SSM before provisioning (see Prerequisites).
- To disable for an environment, set `restrict_to_uk = false` and re-apply (this
  changes `user_data`, which only takes effect on instance replacement — see the
  `ignore_changes = [user_data]` lifecycle note; recreate the instance to apply).

---

## Troubleshooting

### Database import fails mid-way

If `db_importer.py` fails (e.g. due to a malformed VCF or disk space), the database tables will have been truncated and the application will show no data. Re-run `make update-data` with the same arguments to retry the full import.

### Import killed / empty database (exit 137)

On the `t3.large` (8 GB) instance, the database import can be **OOM-killed** (the
web container exits with code 137) if it runs while the live Gunicorn workers are
using memory. Symptom: `make verify-db` reports `variants: 0`, or `make verify-db`
fails with `service "web" is not running`.

Recover by running the import with the web container stopped, then restarting it:

```bash
ssh ubuntu@<ip>
cd ~/genie_nhs_website
docker compose stop web          # free memory
docker compose run --rm web python db_importer.py   # ~3-4 min for v19
docker compose up -d
sqlite3 data/db.sqlite3 'select count(*) from main_variant;'   # expect 1267112
```

To make the box more resilient, add swap (e.g. 4 GB) in `terraform/user_data.sh`
so a future import is not killed under memory pressure.

### Application not functional after `make uat-up`

This is expected. The `user_data.sh` bootstrap starts the Docker container but the `data/` directory is empty. Run `make update-data ENV=uat ...` to load data before testing.

### SSH connection refused

Ensure your SSH key is configured (see [SSH configuration](#ssh-configuration)). The instance may take 2-3 minutes after `make uat-up` to complete bootstrapping. Check progress with:

```bash
ssh ubuntu@<ip> 'tail -20 /var/log/genie-bootstrap.log'
```

### CloudWatch disk alarm shows INSUFFICIENT_DATA

The CloudWatch agent may take up to 5 minutes after instance launch to begin publishing metrics. If the alarm remains in `INSUFFICIENT_DATA` after 10 minutes, SSH in and check the agent status:

```bash
ssh ubuntu@<ip> 'sudo systemctl status amazon-cloudwatch-agent'
```

### SSM `.env` vs live `.env` divergence

The `.env` file on the instance is initially pulled from SSM during provisioning. After running `make update-data`, the data-related variables (`GENIE_VCF`, `GENIE_CANCER_TYPES_CSV`, `GENIE_VERSION`) are updated in-place. If you re-provision the instance (e.g. `terraform destroy` + `terraform apply`), the SSM version will be restored — you'll need to run `make update-data` again.

---

## Makefile Reference

| Target | Required args | Description |
|--------|--------------|-------------|
| `tf-init` | - | Initialise Terraform backend and providers |
| `tf-plan` | `ENV=` | Preview infrastructure changes |
| `tf-apply` | `ENV=` | Apply infrastructure changes |
| `tf-destroy` | `ENV=` | Destroy infrastructure |
| `uat-up` | - | Provision UAT instance (creates workspace if needed) |
| `uat-down` | `ENV=uat` | Destroy UAT instance (guarded - requires `ENV=uat`) |
| `deploy` | `ENV=` | Deploy latest code (git pull + Docker rebuild) |
| `update-data` | `ENV=`, `VCF=`, `CSV=`, `VER=` | Download data from S3 and re-import database |
| `verify-db` | `ENV=` | Check database row counts via SSH |
| `acceptance-test` | `PROD_URL=` (optional) | Run automated known-value + parity tests |
| `acceptance-test-known-values` | `ENV=` | Run known-value tests only |
| `acceptance-checklist` | `PROD_URL=` (optional) | Print manual acceptance checklist |
| `ssl` | `CERTBOT_EMAIL=` (optional) | Run certbot on prod |
| `help` | - | Show all available targets |

Default for `ENV` is `prod`. Run `make help` to see all targets.
