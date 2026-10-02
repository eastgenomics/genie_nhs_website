# Team Onboarding — NHS GENIE Website

This guide takes a new team member from zero access to being able to deploy
code changes and update GENIE data releases. See
[deployment-and-testing.md](deployment-and-testing.md) for the full
infrastructure and deployment reference once you're set up.

---

## Step 1 — Join the Tailscale network

SSH access to all environments (prod/beta/UAT) is restricted to the team's
Tailscale network — instances are not reachable on port 22 from the public
internet.

1. Install Tailscale: https://tailscale.com/download
2. Accept the invite to the **work tailnet** (separate from any personal
   Tailscale account) and sign in
3. Confirm you're on the right tailnet:
   ```bash
   tailscale status
   ```
   You should see `nhs-genie-prod`, `nhs-genie-beta`, `nhs-genie-uat` in the list.

   **If you also use Tailscale personally** on the same machine, you can only
   be connected to one tailnet at a time:
   ```bash
   sudo tailscale switch --list
   sudo tailscale switch <work-tailnet-profile>
   ```

## Step 2 — Get SSH access

> **Known limitation — shared key.** All team members currently use the same
> `nhs-genie.pem` private key, so individual access cannot be revoked without
> rotating the key for everyone. Tailscale-only ingress limits *network*
> reachability, but does not make this SSH credential unique per user.
> Per-user key provisioning is tracked in
> [#42](https://github.com/eastgenomics/genie_nhs_website/issues/42) — until
> then, treat `nhs-genie.pem` with the same care as a production secret and
> rotate it if anyone with access leaves the team.

1. Get the `nhs-genie.pem` private key from whoever onboarded you (shared
   securely, not over chat/email)
2. Save and lock down permissions:
   ```bash
   mkdir -p ~/.ssh
   mv nhs-genie.pem ~/.ssh/
   chmod 600 ~/.ssh/nhs-genie.pem
   ```
3. Find current Tailscale IPs:
   ```bash
   tailscale status | grep nhs-genie
   ```
4. Add to `~/.ssh/config`:
   ```
   Host nhs-genie-prod
     HostName <prod-tailscale-ip>
     User ubuntu
     IdentityFile ~/.ssh/nhs-genie.pem

   Host nhs-genie-beta
     HostName <beta-tailscale-ip>
     User ubuntu
     IdentityFile ~/.ssh/nhs-genie.pem

   Host nhs-genie-uat
     HostName <uat-tailscale-ip>
     User ubuntu
     IdentityFile ~/.ssh/nhs-genie.pem
   ```
5. Test:
   ```bash
   ssh nhs-genie-beta
   ```

## Step 3 — Get AWS access (for uploading new data releases)

Only needed if you'll be uploading new GENIE VCF/CSV files to S3. Skip if
you're only doing code deploys.

Access is granted via an IAM Identity Center permission set
(`GENIEWebsiteDataUpdater`), scoped to read/write on the `genie-website-data`
S3 bucket only — no other AWS access.

1. Ask an admin to add you to the `genie-website-data-updaters` group in IAM
   Identity Center
2. Configure the AWS CLI with SSO:
   ```bash
   aws configure sso
   # SSO start URL: https://<your-sso-portal>.awsapps.com/start
   # SSO region: eu-west-2
   # Account: genie-website (804761969039)
   # Role: GENIEWebsiteDataUpdater
   # CLI profile name: genie-data-updater   (use this exact name — all commands
   #   in this guide and in deployment-and-testing.md assume this profile name)
   ```
3. Log in before each session (SSO tokens expire):
   ```bash
   aws sso login --profile genie-data-updater
   ```
4. Test access:
   ```bash
   AWS_PROFILE=genie-data-updater aws s3 ls s3://genie-website-data/
   ```

## Step 4 — Clone the repo

```bash
git clone https://github.com/eastgenomics/genie_nhs_website.git
cd genie_nhs_website
```

## Step 5 — Deploying a code change

```bash
# After your PR is merged to main:
bash scripts/deploy.sh <prod-tailscale-ip>
```
SSHes in, pulls `main`, rebuilds the Docker container. No AWS credentials
needed — SSH only.

## Step 6 — Updating GENIE data (a new release)

You'll need three things before starting:
1. **S3 URI for the new VCF** (e.g.
   `s3://genie-website-data/GENIE_v21_GRCh38_counts_v1.0.0.vcf.gz`)
2. **S3 URI for the new cancer types CSV**
3. **Confluence page URL** for the signed-off release — used to update
   `scripts/acceptance_expected_values.json` with correct expected values
   before running the import

Upload the files (requires the AWS access from Step 3):
```bash
aws sso login --profile genie-data-updater
AWS_PROFILE=genie-data-updater aws s3 cp GENIE_v21_GRCh38_counts_v1.0.0.vcf.gz s3://genie-website-data/
AWS_PROFILE=genie-data-updater aws s3 cp GENIE_v21_cancer_types.csv s3://genie-website-data/
```

Then update `scripts/acceptance_expected_values.json` from the Confluence
page, commit that change, and run:
```bash
bash scripts/update_data.sh \
  --host <env-tailscale-ip> \
  --vcf  s3://genie-website-data/GENIE_v21_GRCh38_counts_v1.0.0.vcf.gz \
  --csv  s3://genie-website-data/GENIE_v21_cancer_types.csv \
  --version v21 \
  --test-url https://<env-fqdn>
```
`--test-url` automatically runs acceptance tests once the import finishes.

**Always test on UAT or beta first**, then prod. See
[deployment-and-testing.md](deployment-and-testing.md) for the full workflow
and UAT-first checklist.

## Step 7 — Full documentation

Read [deployment-and-testing.md](deployment-and-testing.md) for infrastructure
setup (Terraform), SSL renewal, troubleshooting, and the complete example
deployment session.
