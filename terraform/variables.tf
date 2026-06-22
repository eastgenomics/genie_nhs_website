variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-2"
}

variable "key_pair_name" {
  description = "Name of an existing EC2 key pair"
  type        = string
}

variable "domain" {
  description = "Delegated domain for the hosted zone (e.g. genie.genomics-resources.uk). Prod uses this directly; UAT uses uat.<domain>."
  type        = string
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID for var.domain"
  type        = string
}

variable "s3_data_bucket" {
  description = "S3 bucket containing GENIE VCF and cancer types CSV"
  type        = string
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
}

variable "alert_slack_email" {
  description = "Optional Slack email integration address for CloudWatch alarm notifications"
  type        = string
  default     = ""
}

variable "ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH (e.g. office/VPN range). No default — must be set explicitly."
  type        = list(string)
}

variable "github_repo" {
  description = "GitHub repository URL to clone on the instance"
  type        = string
  default     = "https://github.com/eastgenomics/genie_nhs_website.git"
}

variable "ssm_env_parameter" {
  description = "SSM parameter path prefix for .env files (appended with /{env}/env)"
  type        = string
  default     = "/genie"
}

# --- UK geo-restriction (Nginx GeoIP2) ---

variable "restrict_to_uk" {
  description = "Restrict HTTP/HTTPS access to allowed_countries using Nginx GeoIP2. When true, requests from other countries receive HTTP 403."
  type        = bool
  default     = true
}

variable "allowed_countries" {
  description = "ISO 3166-1 alpha-2 country codes permitted when restrict_to_uk is true. Defaults to the UK plus the Crown Dependencies (Isle of Man, Jersey, Guernsey)."
  type        = list(string)
  default     = ["GB", "IM", "JE", "GG"]
}

variable "maxmind_ssm_parameter" {
  description = "SSM SecureString parameter holding the MaxMind GeoLite2 licence key, used to download the GeoLite2-Country database on the instance."
  type        = string
  default     = "/genie/maxmind/license_key"
}
