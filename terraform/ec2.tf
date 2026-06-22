data "aws_key_pair" "genie" {
  key_name = var.key_pair_name
}

# --- Latest Canonical Ubuntu 24.04 LTS AMI (amd64) ---
# Looked up at plan time so the AMI ID does not need hardcoding per account.
# aws_instance.genie has lifecycle.ignore_changes = [ami] so a newer AMI
# appearing here will not force replacement of a running instance.

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}

# --- Security group ---

resource "aws_security_group" "genie" {
  name        = "${local.name}-sg"
  description = "Security group for NHS GENIE ${local.env}"

  tags = { Name = "${local.name}-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.genie.id
  description       = "SSH"
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  cidr_ipv4         = var.ssh_cidr_blocks[0]
}

resource "aws_vpc_security_group_ingress_rule" "ssh_extra" {
  count             = length(var.ssh_cidr_blocks) > 1 ? length(var.ssh_cidr_blocks) - 1 : 0
  security_group_id = aws_security_group.genie.id
  description       = "SSH additional CIDR"
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  cidr_ipv4         = var.ssh_cidr_blocks[count.index + 1]
}

resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.genie.id
  description       = "HTTP"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.genie.id
  description       = "HTTPS"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

# --- Egress rules (least-privilege) ---
# Replaces the previous catch-all rule (ip_protocol = "-1") to satisfy
# Trivy AWS-0104. Only ports confirmed as necessary by user_data.sh are opened.

resource "aws_vpc_security_group_egress_rule" "egress_https" {
  security_group_id = aws_security_group.genie.id
  description       = "HTTPS outbound (apt, Docker, AWS APIs, GitHub, MaxMind, PyPI)"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "egress_http" {
  security_group_id = aws_security_group.genie.id
  description       = "HTTP outbound (apt mirrors, Lets Encrypt ACME challenge)"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "egress_dns" {
  security_group_id = aws_security_group.genie.id
  description       = "DNS resolution (UDP) to VPC resolver"
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
  cidr_ipv4         = "169.254.169.253/32"
}

resource "aws_vpc_security_group_egress_rule" "egress_dns_tcp" {
  security_group_id = aws_security_group.genie.id
  description       = "DNS resolution (TCP) to VPC resolver - large responses"
  from_port         = 53
  to_port           = 53
  ip_protocol       = "tcp"
  cidr_ipv4         = "169.254.169.253/32"
}

resource "aws_vpc_security_group_egress_rule" "egress_ntp" {
  security_group_id = aws_security_group.genie.id
  description       = "NTP time sync (UDP) to AWS time sync service"
  from_port         = 123
  to_port           = 123
  ip_protocol       = "udp"
  cidr_ipv4         = "169.254.169.123/32"
}

# --- EC2 instance ---

resource "aws_instance" "genie" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = local.ec2_type
  key_name               = data.aws_key_pair.genie.key_name
  vpc_security_group_ids = [aws_security_group.genie.id]
  iam_instance_profile   = aws_iam_instance_profile.genie.name

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_size = local.ebs_gb
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    environment           = local.env
    ssm_env_parameter     = "${var.ssm_env_parameter}/${local.env}/env"
    github_repo           = var.github_repo
    aws_region            = var.aws_region
    restrict_to_uk        = var.restrict_to_uk
    allowed_countries     = join(" ", var.allowed_countries)
    maxmind_ssm_parameter = var.maxmind_ssm_parameter
  })

  tags = { Name = local.name }

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

# --- Elastic IP (prod only) ---

resource "aws_eip" "genie" {
  count    = local.is_prod ? 1 : 0
  instance = aws_instance.genie.id
  domain   = "vpc"

  tags = { Name = "${local.name}-eip" }
}
