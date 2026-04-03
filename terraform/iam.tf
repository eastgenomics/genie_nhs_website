data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "genie" {
  name               = "${local.name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = { Name = "${local.name}-ec2-role" }
}

resource "aws_iam_instance_profile" "genie" {
  name = "${local.name}-instance-profile"
  role = aws_iam_role.genie.name
}

# --- S3 read access to the GENIE data bucket ---

data "aws_iam_policy_document" "s3_read" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${var.s3_data_bucket}/*"]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.s3_data_bucket}"]
  }
}

resource "aws_iam_role_policy" "s3_read" {
  name   = "${local.name}-s3-read"
  role   = aws_iam_role.genie.id
  policy = data.aws_iam_policy_document.s3_read.json
}

# --- SSM Parameter Store read access for .env secrets ---

data "aws_iam_policy_document" "ssm_read" {
  statement {
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_env_parameter}/*"]
  }
}

resource "aws_iam_role_policy" "ssm_read" {
  name   = "${local.name}-ssm-read"
  role   = aws_iam_role.genie.id
  policy = data.aws_iam_policy_document.ssm_read.json
}

# --- CloudWatch agent permissions ---

data "aws_iam_policy_document" "cloudwatch_agent" {
  statement {
    actions = [
      "cloudwatch:PutMetricData",
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["*"]
  }
  statement {
    actions   = ["ec2:DescribeVolumes", "ec2:DescribeInstances", "ec2:DescribeTags"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "cloudwatch_agent" {
  name   = "${local.name}-cw-agent"
  role   = aws_iam_role.genie.id
  policy = data.aws_iam_policy_document.cloudwatch_agent.json
}
