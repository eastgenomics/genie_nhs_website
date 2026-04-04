# Beta v19 Deployment Notes

## Status: BLOCKED

The beta site at `beta.genie.genomics-resources.uk` (16.60.13.139) is provisioned
but v19 data import is blocked by app changes needed to support the v19 VCF format.

## What's done

### Infrastructure
- Terraform FQDN fix: non-prod workspaces now use `${workspace}.genie.genomics-resources.uk`
  (was hardcoded to `uat.genie.genomics-resources.uk`)
- Beta EC2 instance provisioned in `genie-website` account via `terraform workspace new beta`
- SSM parameter `/genie/beta/env` created
- GENIE v19 VCF and cancer_types_v19.csv uploaded to `genie-website-data` S3 bucket

### Scripts
- `scripts/generate_cancer_types_csv.py` — generates `cancer_types.csv` from a VCF and
  haemonc/solid txt files. Used to produce `cancer_types_v19.csv` (115 cancer types,
  1 new: PeripheralNervousSystemCancer, classified as solid)
- SSH key support added to Makefile (`SSH_KEY` variable) and all scripts (`--ssh-opts`)
- `deploy.sh` / `update_data.sh` — fixed `docker compose run` stdin consumption in SSH
  heredocs (added `-T` and `< /dev/null`)
- `update_data.sh` — removed `set -u` from SSH heredoc (caused silent failures)

### Bug fixes to db_importer.py
- Fixed parsing of v19 VCF `Duplicate_Patient_IDs` fields that share the
  `SameNucleotideChange_` prefix but are not patient count fields
- Added `_Count_N_` check before stripping the count suffix
- Added `cancer_type_ids` lookup before attempting `int(val)` conversion

## What's blocked

The v19 VCF intentionally removed `Variant_Classification` (and `Variant_Type`, `Strand`,
`Transcript_ID`). The app's classification system (`get_classification_category()` in
`utils.py`) relies on MAF-style terms from this field.

The app must be updated to derive classification categories from the VEP `Consequence`
field instead. This is tracked as a separate piece of work.

See: https://cuhbioinformatics.atlassian.net/wiki/spaces/DV/pages/4426629121/

### Mapping needed: MAF classification -> VEP consequence

| Current (MAF) | VEP SO term(s) |
|---|---|
| Frame_Shift_Del | frameshift_variant |
| Frame_Shift_Ins | frameshift_variant |
| Nonsense_Mutation | stop_gained |
| Splice_Site | splice_acceptor_variant, splice_donor_variant |
| In_Frame_Ins | inframe_insertion |
| In_Frame_Del | inframe_deletion |
| Missense_Mutation | missense_variant |
| Nonstop_Mutation | stop_lost |
| Translation_Start_Site | start_lost |
| Silent | synonymous_variant |

## To resume

Once the app classification changes are merged:

```bash
# Rebuild Docker image on beta instance with updated code
AWS_PROFILE=genie-website make deploy ENV=beta

# Re-run data import
AWS_PROFILE=genie-website make update-data ENV=beta \
  VCF=s3://genie-website-data/GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz \
  CSV=s3://genie-website-data/cancer_types_v19.csv \
  VER=v19

# Verify and set up HTTPS
AWS_PROFILE=genie-website make verify-db ENV=beta
AWS_PROFILE=genie-website make ssl ENV=beta
```
