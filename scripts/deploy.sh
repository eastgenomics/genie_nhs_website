#!/bin/bash
set -euo pipefail

# Deploy the NHS GENIE application on a remote host.
# Usage: scripts/deploy.sh <host-ip>

HOST="${1:?Usage: deploy.sh <host-ip>}"
SSH_USER="ubuntu"
APP_DIR="/home/ubuntu/genie_nhs_website"

echo "Deploying to ${SSH_USER}@${HOST}..."

ssh "${SSH_USER}@${HOST}" bash <<EOF
  set -euo pipefail
  cd "${APP_DIR}"

  echo "Pulling latest code..."
  git pull origin main

  echo "Pruning old Docker images..."
  docker system prune -a --force

  echo "Building and starting containers..."
  docker compose up --build -d

  echo "Waiting for health check..."
  for i in \$(seq 1 30); do
    sleep 2
    if docker compose ps --format json | grep -q '"Health":"healthy"'; then
      echo "Deployment successful - container is healthy."
      exit 0
    fi
  done
  echo "WARNING: container not healthy after 60s. Check: docker compose logs"
  exit 1
EOF

echo "Done."
