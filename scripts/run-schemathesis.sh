#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-test}"
ENV_FILE="${2:-.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Environment file '${ENV_FILE}' not found. Copy .env.example to ${ENV_FILE} and edit it or define environment otherwise."
else
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

case "${ENVIRONMENT}" in
  test|testing)
    BASE_URL="${TEST_BASE_URL:-}"
    USER_TOKEN="${TEST_USER_TOKEN:-}"
    SHAREE_ACCOUNT="${TEST_SHAREE_ACCOUNT:-}"
    ;;
  prod|production)
    BASE_URL="${PROD_BASE_URL:-}"
    USER_TOKEN="${PROD_USER_TOKEN:-}"
    SHAREE_ACCOUNT="${PROD_SHAREE_ACCOUNT:-}"
    ;;
  *)
    echo "Unknown environment '${ENVIRONMENT}'. Use 'test' or 'production'."
    exit 1
    ;;
esac

if [[ -z "${BASE_URL}" ]]; then
  echo "BASE_URL for '${ENVIRONMENT}' is not set in ${ENV_FILE}."
  exit 1
fi

if [[ -z "${USER_TOKEN}" ]]; then
  echo "USER_TOKEN for '${ENVIRONMENT}' is not set in ${ENV_FILE}."
  exit 1
fi

if [[ -z "${SHAREE_ACCOUNT}" ]]; then
  echo "SHAREE_ACCOUNT for '${ENVIRONMENT}' is not set in ${ENV_FILE}."
  exit 1
fi

uvx schemathesis run userapi/bundle.yaml \
  --url "${BASE_URL}" \
  --header "Authorization: ${USER_TOKEN}" \