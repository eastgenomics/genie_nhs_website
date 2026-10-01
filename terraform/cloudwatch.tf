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

resource "aws_sns_topic_subscription" "slack_email" {
  count     = local.is_prod && var.alert_slack_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.genie_alerts[0].arn
  protocol  = "email"
  endpoint  = var.alert_slack_email
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
# "disk_used_percent" metric (configured in user_data.sh). The agent config
# uses aggregation_dimensions [[InstanceId, path]] so the published metric has
# exactly the InstanceId + path dimensions this alarm matches on.

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
  }
  alarm_actions       = [aws_sns_topic.genie_alerts[0].arn]
  ok_actions          = [aws_sns_topic.genie_alerts[0].arn]
}

# --- TLS certificate expiry alarm (<21 days remaining) ---
# Fed by /usr/local/bin/check-cert-expiry.sh on the instance (installed by
# user_data.sh, run every 6h by cert-expiry-metric.timer), which measures the
# certificate as served by Nginx on localhost:443.
#
# Let's Encrypt certs are 90 days and certbot renews at 30 days remaining, so a
# healthy instance never drops below ~30 and 21 gives three weeks of warning
# without false positives.
#
# treat_missing_data = "breaching" is deliberate: if the publishing timer itself
# dies, that is exactly the silent-failure mode this alarm exists to catch, so
# absent data must alert rather than sit in INSUFFICIENT_DATA.

resource "aws_cloudwatch_metric_alarm" "cert_expiry" {
  count               = local.is_prod ? 1 : 0
  alarm_name          = "${local.name}-cert-expiry"
  alarm_description   = "TLS certificate expires in <21 days - check certbot-renew.timer on the instance"
  namespace           = "Genie"
  metric_name         = "CertDaysToExpiry"
  statistic           = "Minimum"
  period              = 21600
  evaluation_periods  = 2
  threshold           = 21
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  dimensions = {
    InstanceId = aws_instance.genie.id
  }
  alarm_actions = [aws_sns_topic.genie_alerts[0].arn]
  ok_actions    = [aws_sns_topic.genie_alerts[0].arn]
}
