#!/bin/bash
set -euo pipefail

# Log all output for debugging via:
#   sudo cat /var/log/cloud-init-output.log
exec > >(tee /var/log/genie-bootstrap.log) 2>&1

echo "=== NHS GENIE bootstrap (${environment}) ==="

export DEBIAN_FRONTEND=noninteractive

# --- Configure swap ---
# The t3.large has 8 GB RAM; the GENIE DB import (~1.27M variants) can push the
# box into OOM if it runs alongside the live Gunicorn workers. A few GB of swap
# makes memory-heavy operations (imports, apt upgrades) resilient.
if ! swapon --show | grep -q '/swapfile'; then
  fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
  sysctl -w vm.swappiness=10
fi

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

# --- Install AWS CLI (needed early for SSM lookups below) ---
apt-get install -y unzip
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/aws /tmp/awscliv2.zip

# --- Install and configure Nginx as reverse proxy ---
apt-get install -y nginx

%{ if restrict_to_uk ~}
# --- UK geo-restriction via Nginx GeoIP2 ---
# Install the dynamic GeoIP2 module and download the GeoLite2-Country database
# using the MaxMind licence key stored in SSM (maxmind_ssm_parameter).
apt-get install -y libnginx-mod-http-geoip2

mkdir -p /etc/nginx/geoip

# Write a refresh script that pulls the licence key from SSM and downloads the DB
cat > /usr/local/bin/update-geolite2.sh <<'UPDATE'
#!/bin/bash
set -euo pipefail
KEY=$(aws ssm get-parameter --name "__MAXMIND_PARAM__" --with-decryption --query "Parameter.Value" --output text --region "__AWS_REGION__")
curl -fsSL "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country&license_key=$${KEY}&suffix=tar.gz" -o /tmp/geolite.tar.gz
tar -xzf /tmp/geolite.tar.gz -C /tmp
find /tmp -name 'GeoLite2-Country.mmdb' -exec cp {} /etc/nginx/geoip/GeoLite2-Country.mmdb \;
rm -rf /tmp/geolite.tar.gz /tmp/GeoLite2-Country_*
UPDATE
sed -i "s|__MAXMIND_PARAM__|${maxmind_ssm_parameter}|g; s|__AWS_REGION__|${aws_region}|g" /usr/local/bin/update-geolite2.sh
chmod +x /usr/local/bin/update-geolite2.sh

# Initial download
/usr/local/bin/update-geolite2.sh

# Weekly refresh (Mondays 04:00)
cat > /etc/cron.d/update-geolite2 <<'CRON'
0 4 * * 1 root /usr/local/bin/update-geolite2.sh >/var/log/geolite2-update.log 2>&1 && systemctl reload nginx
CRON

# GeoIP2 lookup + allowed-country map (http context, included by nginx.conf)
cat > /etc/nginx/conf.d/geoip2.conf <<'GEOIP2'
geoip2 /etc/nginx/geoip/GeoLite2-Country.mmdb {
    $geoip2_country_iso_code source=$remote_addr country iso_code;
}

map $geoip2_country_iso_code $allowed_country {
    default no;
%{ for code in split(" ", allowed_countries) ~}
    ${code} yes;
%{ endfor ~}
}
GEOIP2
%{ endif ~}

cat > /etc/nginx/sites-available/genie <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
%{ if restrict_to_uk ~}

    # Reject requests from outside the allowed countries (UK + Crown Dependencies)
    if ($allowed_country = no) {
        return 403;
    }
%{ endif ~}

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/genie /etc/nginx/sites-enabled/genie
systemctl enable --now nginx
nginx -t && systemctl reload nginx

# --- Install certbot ---
apt-get install -y python3-venv libaugeas-dev
python3 -m venv /opt/certbot/
/opt/certbot/bin/pip install --upgrade pip
/opt/certbot/bin/pip install certbot certbot-nginx
ln -sf /opt/certbot/bin/certbot /usr/bin/certbot

# A pip/venv certbot install does NOT create a renewal timer (only the snap and
# Debian packages do), so install one explicitly. Without this, certificates
# silently expire 90 days after issuance.
cat > /etc/systemd/system/certbot-renew.service <<'CERTBOTSVC'
[Unit]
Description=Renew Let's Encrypt certificates
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --nginx
CERTBOTSVC

cat > /etc/systemd/system/certbot-renew.timer <<'CERTBOTTIMER'
[Unit]
Description=Run certbot renew twice daily

[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
CERTBOTTIMER

systemctl daemon-reload
systemctl enable --now certbot-renew.timer

# --- Certificate expiry metric ---
# Publishes days-until-expiry to CloudWatch so a silent renewal failure is
# caught. Deliberately measures the certificate *as served by Nginx* rather
# than the PEM on disk, so it also catches "certbot renewed but Nginx was
# never reloaded".
cat > /usr/local/bin/check-cert-expiry.sh <<'CERTCHECK'
#!/bin/bash
set -uo pipefail

FQDN="__FQDN__"
REGION="__AWS_REGION__"

# IMDSv2 is enforced on this instance, so a token is required.
TOKEN=$(curl -fsS -m 5 -X PUT http://169.254.169.254/latest/api/token \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' 2>/dev/null || true)
INSTANCE_ID=$(curl -fsS -m 5 -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo unknown)

NOT_AFTER=$(echo | timeout 15 openssl s_client -connect 127.0.0.1:443 -servername "$FQDN" 2>/dev/null \
  | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)

if [ -z "$${NOT_AFTER:-}" ]; then
  # No certificate could be read at all. Report 0 rather than publishing
  # nothing, so the alarm goes to ALARM instead of INSUFFICIENT_DATA.
  DAYS=0
else
  DAYS=$(( ( $(date -d "$NOT_AFTER" +%s) - $(date +%s) ) / 86400 ))
  [ "$DAYS" -lt 0 ] && DAYS=0
fi

aws cloudwatch put-metric-data \
  --region "$REGION" \
  --namespace Genie \
  --metric-name CertDaysToExpiry \
  --unit Count \
  --value "$DAYS" \
  --dimensions InstanceId="$INSTANCE_ID" || exit "$?"

logger -t check-cert-expiry "CertDaysToExpiry=$DAYS (notAfter=$${NOT_AFTER:-unavailable})"
CERTCHECK
sed -i "s|__FQDN__|${fqdn}|g; s|__AWS_REGION__|${aws_region}|g" /usr/local/bin/check-cert-expiry.sh
chmod +x /usr/local/bin/check-cert-expiry.sh

cat > /etc/systemd/system/cert-expiry-metric.service <<'CERTMETRICSVC'
[Unit]
Description=Publish TLS certificate days-to-expiry to CloudWatch
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/check-cert-expiry.sh
CERTMETRICSVC

cat > /etc/systemd/system/cert-expiry-metric.timer <<'CERTMETRICTIMER'
[Unit]
Description=Publish TLS certificate expiry metric every 6 hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:30:00
OnBootSec=10min
Persistent=true

[Install]
WantedBy=timers.target
CERTMETRICTIMER

systemctl daemon-reload
systemctl enable --now cert-expiry-metric.timer

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
    "aggregation_dimensions": [["InstanceId", "path"]],
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
chmod 777 staticfiles data

# Fix ownership so ubuntu user can manage the app via SSH
chown -R ubuntu:ubuntu /home/ubuntu/genie_nhs_website

# Build, run migrations, and start the application
docker compose run --rm web python manage.py migrate --noinput
docker compose up --build -d

echo "=== NHS GENIE bootstrap complete ==="
