output "public_ip" {
  description = "Public IP of the instance (Elastic IP for prod, ephemeral for UAT)"
  value       = local.is_prod ? aws_eip.genie[0].public_ip : aws_instance.genie.public_ip
}

output "public_dns" {
  description = "Public DNS of the instance"
  value       = aws_instance.genie.public_dns
}

output "fqdn" {
  description = "Fully qualified domain name"
  value       = local.fqdn
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.genie.id
}
