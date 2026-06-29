# AWS account: genie-website (804761969039)
# The Ubuntu 24.04 LTS AMI is looked up automatically (see data.aws_ami.ubuntu
# in ec2.tf) so no ami_id is set here.
key_pair_name   = "nhs-genie"
domain          = "genie.genomics-resources.uk"
route53_zone_id = "Z09949371PEDMO2FEKH29"
s3_data_bucket  = "genie-website-data"
alert_email     = "cuh.bioinformatics.group@nhs.net"
# alert_slack_email is intentionally omitted from VCS — pass it at apply time:
#   terraform apply -var="alert_slack_email=<slack-channel-email>"
# See variables.tf: defaults to "" (subscription skipped) if not supplied.
ssh_cidr_blocks = ["145.40.188.80/32"]

# UK geo-restriction (Nginx GeoIP2). Requires the MaxMind GeoLite2 licence key
# to be stored in SSM at maxmind_ssm_parameter (default /genie/maxmind/license_key).
restrict_to_uk    = true
allowed_countries = ["GB", "IM", "JE", "GG"]
