#!/bin/bash
set -euo pipefail

# Download new GENIE data from S3 and re-import the database.
# Usage: scripts/update_data.sh --host <ip> --vcf <s3-uri> --csv <s3-uri> --version <string>

usage() {
    echo "Usage: $0 --host <ip> --vcf <s3-uri> --csv <s3-uri> --version <string>"
    exit 1
}

HOST="" VCF="" CSV="" VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)    HOST="$2";    shift 2 ;;
        --vcf)     VCF="$2";     shift 2 ;;
        --csv)     CSV="$2";     shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        *)         usage ;;
    esac
done

[[ -z "$HOST" || -z "$VCF" || -z "$CSV" || -z "$VERSION" ]] && usage

SSH_USER="ubuntu"
APP_DIR="/home/ubuntu/genie_nhs_website"
VCF_FILENAME=$(basename "$VCF")
CSV_FILENAME=$(basename "$CSV")

# Validate filenames don't contain characters that would break sed
for name in "$VCF_FILENAME" "$CSV_FILENAME" "$VERSION"; do
    if [[ "$name" =~ [|\\] ]]; then
        echo "ERROR: filename or version contains unsafe characters: $name"
        exit 1
    fi
done

echo "Updating data on ${SSH_USER}@${HOST}..."
echo "  VCF: ${VCF}"
echo "  CSV: ${CSV}"
echo "  Version: ${VERSION}"

ssh "${SSH_USER}@${HOST}" bash <<EOF
  set -euo pipefail
  cd "${APP_DIR}"

  echo "Verifying AWS credentials..."
  aws sts get-caller-identity > /dev/null

  echo "Downloading VCF from S3..."
  aws s3 cp "${VCF}" "./data/${VCF_FILENAME}"

  echo "Downloading cancer types CSV from S3..."
  aws s3 cp "${CSV}" "./data/${CSV_FILENAME}"

  echo "Updating .env with new file references..."
  sed -i "s|^GENIE_VCF=.*|GENIE_VCF=${VCF_FILENAME}|" .env
  sed -i "s|^GENIE_CANCER_TYPES_CSV=.*|GENIE_CANCER_TYPES_CSV=${CSV_FILENAME}|" .env
  sed -i "s|^GENIE_VERSION=.*|GENIE_VERSION=${VERSION}|" .env

  echo "Stopping application (downtime starts)..."
  docker compose stop

  echo "Running database import..."
  docker compose run --rm web python db_importer.py

  echo "Starting application..."
  docker compose up -d

  echo "Data update complete (downtime ended)."
EOF

echo "Done. Run 'make verify-db' to check row counts."
