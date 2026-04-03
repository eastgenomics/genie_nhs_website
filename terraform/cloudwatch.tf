# CloudWatch alarms are only created for prod.

# --- SNS topic for alarm notifications ---

resource "aws_sns_topic" "genie_alerts" {
  count = local.is_prod ? 1 : 0
  name  = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = local.is_prod ? 1 : 0
  topic_arn = aws_sns_topic.genie_alerts[0].arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# --- CPU utilisation alarm (>80% for 5 minutes) ---

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  count               = local.is_prod ? 1 : 0
  alarm_name          = "${local.name}-cpu-high"
  alarm_description   = "CPU utilisation >80% for 5 minutes"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  dimensions = {
    InstanceId = aws_instance.genie.id
  }
  alarm_actions = [aws_sns_topic.genie_alerts[0].arn]
  ok_actions    = [aws_sns_topic.genie_alerts[0].arn]
}

# --- Disk usage alarm (>80%) ---
# Requires the CloudWatch agent to be running and publishing the
# "disk_used_percent" metric (configured in user_data.sh).

resource "aws_cloudwatch_metric_alarm" "disk_high" {
  count               = local.is_prod ? 1 : 0
  alarm_name          = "${local.name}-disk-high"
  alarm_description   = "Root volume disk usage >80%"
  namespace           = "CWAgent"
  metric_name         = "disk_used_percent"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  dimensions = {
    InstanceId = aws_instance.genie.id
    path       = "/"
    device     = "nvme0n1p1"
    fstype     = "ext4"
  }
  alarm_actions = [aws_sns_topic.genie_alerts[0].arn]
  ok_actions    = [aws_sns_topic.genie_alerts[0].arn]
}
