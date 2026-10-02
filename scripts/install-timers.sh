#!/bin/bash
# install-timers.sh
# Run this on the prod instance to install the certbot renewal timer and the
# cert-expiry CloudWatch metric timer. These units are baked into user_data.sh
# but user_data only runs on first boot — this script backfills the live instance.
#
# Usage (from your local machine, with ssh-agent loaded):
#   ssh ubuntu@<prod-ip> 'bash -s' < scripts/install-timers.sh

set -euo pipefail

# --- certbot-renew timer ---

sudo tee /etc/systemd/system/certbot-renew.service > /dev/null <<'CERTBOTSVC'
[Unit]
Description=Renew Let's Encrypt certificates
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --nginx
CERTBOTSVC

sudo tee /etc/systemd/system/certbot-renew.timer > /dev/null <<'CERTBOTTIMER'
[Unit]
Description=Run certbot renew twice daily

[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
CERTBOTTIMER

sudo systemctl daemon-reload
sudo systemctl enable --now certbot-renew.timer

echo "certbot-renew.timer installed:"
systemctl list-timers certbot-renew.timer --no-pager

# --- check-cert-expiry.sh ---

sudo tee /usr/local/bin/check-cert-expiry.sh > /dev/null <<'CERTCHECK'
#!/bin/bash
set -uo pipefail

FQDN="genie.genomics-resources.uk"
REGION="eu-west-2"

# IMDSv2 is enforced on this instance, so a token is required.
TOKEN=$(curl -fsS -m 5 -X PUT http://169.254.169.254/latest/api/token \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' 2>/dev/null || true)
INSTANCE_ID=$(curl -fsS -m 5 -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo unknown)

NOT_AFTER=$(echo | timeout 15 openssl s_client -connect 127.0.0.1:443 -servername "$FQDN" 2>/dev/null \
  | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)

if [ -z "${NOT_AFTER:-}" ]; then
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

logger -t check-cert-expiry "CertDaysToExpiry=$DAYS (notAfter=${NOT_AFTER:-unavailable})"
CERTCHECK

sudo chmod +x /usr/local/bin/check-cert-expiry.sh

# --- cert-expiry-metric timer ---

sudo tee /etc/systemd/system/cert-expiry-metric.service > /dev/null <<'CERTMETRICSVC'
[Unit]
Description=Publish TLS certificate days-to-expiry to CloudWatch
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/check-cert-expiry.sh
CERTMETRICSVC

sudo tee /etc/systemd/system/cert-expiry-metric.timer > /dev/null <<'CERTMETRICTIMER'
[Unit]
Description=Publish TLS certificate expiry metric every 6 hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:30:00
OnBootSec=10min
Persistent=true

[Install]
WantedBy=timers.target
CERTMETRICTIMER

sudo systemctl daemon-reload
sudo systemctl enable --now cert-expiry-metric.timer

echo "cert-expiry-metric.timer installed:"
systemctl list-timers cert-expiry-metric.timer --no-pager

# --- Smoke test: run the metric check now ---
echo ""
echo "Running check-cert-expiry.sh now..."
sudo /usr/local/bin/check-cert-expiry.sh
journalctl -t check-cert-expiry -n 1 --no-pager

echo ""
echo "Done. Both timers are installed and enabled."
echo "Verify in CloudWatch: Genie/CertDaysToExpiry (allow ~1 min to propagate)."
