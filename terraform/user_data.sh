#!/bin/bash
set -euo pipefail

# Log all output for debugging via:
#   sudo cat /var/log/cloud-init-output.log
exec > >(tee /var/log/genie-bootstrap.log) 2>&1

echo "=== NHS GENIE bootstrap (${environment}) ==="

export DEBIAN_FRONTEND=noninteractive

# --- System updates ---
apt-get update -y
apt-get upgrade -y

# --- Install Docker ---
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
usermod -aG docker ubuntu

# --- Install Nginx ---
apt-get install -y nginx
systemctl enable --now nginx

# --- Install AWS CLI ---
apt-get install -y unzip
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/aws /tmp/awscliv2.zip

# --- Install and configure CloudWatch agent ---
wget -q https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb \
  -O /tmp/amazon-cloudwatch-agent.deb
dpkg -i /tmp/amazon-cloudwatch-agent.deb
rm /tmp/amazon-cloudwatch-agent.deb

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'CWCONFIG'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "root"
  },
  "metrics": {
    "namespace": "CWAgent",
    "append_dimensions": {
      "InstanceId": "$${aws:InstanceId}"
    },
    "metrics_collected": {
      "disk": {
        "measurement": ["used_percent"],
        "metrics_collection_interval": 60,
        "resources": ["/"]
      },
      "mem": {
        "measurement": ["mem_used_percent"],
        "metrics_collection_interval": 60
      }
    }
  }
}
CWCONFIG

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s

systemctl enable amazon-cloudwatch-agent

# --- Pull .env from SSM Parameter Store ---
APP_DIR="/home/ubuntu/genie_nhs_website"

aws ssm get-parameter \
  --name "${ssm_env_parameter}" \
  --with-decryption \
  --query "Parameter.Value" \
  --output text \
  --region "${aws_region}" \
  > /tmp/genie.env

# --- Clone repo and deploy ---
cd /home/ubuntu
git clone "${github_repo}" genie_nhs_website
cd "$APP_DIR"

cp /tmp/genie.env .env
rm /tmp/genie.env

mkdir -p staticfiles data
chmod 775 staticfiles

# Fix ownership so ubuntu user can manage the app via SSH
chown -R ubuntu:ubuntu /home/ubuntu/genie_nhs_website

# Build and start the application
docker compose up --build -d

echo "=== NHS GENIE bootstrap complete ==="
