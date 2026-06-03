resource "aws_route53_record" "genie" {
  zone_id = var.route53_zone_id
  name    = local.fqdn
  type    = "A"
  ttl     = 60
  records = [local.is_prod ? aws_eip.genie[0].public_ip : aws_instance.genie.public_ip]
}
