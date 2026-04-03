data "aws_key_pair" "genie" {
  key_name = var.key_pair_name
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

resource "aws_vpc_security_group_egress_rule" "all_outbound" {
  security_group_id = aws_security_group.genie.id
  description       = "All outbound"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# --- EC2 instance ---

resource "aws_instance" "genie" {
  ami                    = var.ami_id
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
    environment       = local.env
    ssm_env_parameter = "${var.ssm_env_parameter}/${local.env}/env"
    github_repo       = var.github_repo
    aws_region        = var.aws_region
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
