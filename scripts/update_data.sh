#!/bin/bash
set -euo pipefail

# Download new GENIE data from S3 and re-import the database.
# Usage: scripts/update_data.sh --host <ip> --vcf <s3-uri> --csv <s3-uri> --version <string>

usage() {
    echo "Usage: $0 --host <ip> --vcf <s3-uri> --csv <s3-uri> --version <string> [--test-url <https://fqdn>]"
    exit 1
}

HOST="" VCF="" CSV="" VERSION="" TEST_URL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)     HOST="$2";     shift 2 ;;
        --vcf)      VCF="$2";      shift 2 ;;
        --csv)      CSV="$2";      shift 2 ;;
        --version)  VERSION="$2";  shift 2 ;;
        --test-url) TEST_URL="$2"; shift 2 ;;
        *)          usage ;;
    esac
done

[[ -z "$HOST" || -z "$VCF" || -z "$CSV" || -z "$VERSION" ]] && usage

SSH_USER="ubuntu"
APP_DIR="/home/ubuntu/genie_nhs_website"
VCF_FILENAME=$(basename "$VCF")
CSV_FILENAME=$(basename "$CSV")

# Validate filenames don't contain characters that would break sed
unsafe_pattern='[|\\&]'
for name in "$VCF_FILENAME" "$CSV_FILENAME" "$VERSION"; do
    if [[ "$name" =~ $unsafe_pattern ]] || [[ "$name" == *$'\n'* ]] || [[ "$name" == *$'\r'* ]]; then
        echo "ERROR: filename or version contains unsafe sed characters: $name"
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

  # The script itself arrives on stdin, so every \`docker compose run\` below
  # reads from /dev/null; otherwise it swallows the rest of this script and
  # the import and restart steps silently never run
  echo "Stopping application (downtime starts)..."
  docker compose stop

  echo "Running migrations..."
  docker compose run --rm -T web python manage.py migrate --noinput < /dev/null

  echo "Running database import..."
  docker compose run --rm -T web python db_importer.py < /dev/null

  echo "Verifying row counts..."
  docker compose run --rm -T web python manage.py shell -c "
from main.models import Variant, CancerType
v = Variant.objects.count()
c = CancerType.objects.count()
assert v > 0, 'ERROR: No variants imported'
assert c > 0, 'ERROR: No cancer types imported'
print('Variants:', v)
print('CancerTypes:', c)
" < /dev/null

  echo "Starting application..."
  docker compose up -d

  echo "Data update complete (downtime ended)."
EOF

if [ -n "${TEST_URL}" ]; then
    # docker compose up -d returns before gunicorn is serving, so wait for
    # the site to respond before testing (nginx returns 502 until then)
    echo "Waiting for ${TEST_URL} to come back up..."
    for _ in $(seq 1 24); do
        status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${TEST_URL}" || true)
        [[ "$status" == "200" ]] && break
        sleep 5
    done
    if [[ "$status" != "200" ]]; then
        echo "ERROR: ${TEST_URL} did not return 200 within 2 minutes (last status: ${status})"
        echo "Check the container on the host: docker compose ps -a && docker compose logs web"
        exit 1
    fi

    echo "Running acceptance tests against ${TEST_URL}..."
    python3 "$(dirname "$0")/acceptance_test.py" \
        --uat-url "${TEST_URL}" \
        --mode known-values
else
    echo "Skipping acceptance tests (no --test-url supplied)."
    echo "Run manually: make acceptance-test-known-values ENV=<env>"
fi

echo "Done. Run 'make verify-db' to check row counts."
