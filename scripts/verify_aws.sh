#!/usr/bin/env bash
set -euo pipefail

if ! command -v aws >/dev/null 2>&1; then
  echo "UNVERIFIED: AWS CLI is not installed." >&2
  exit 2
fi

VERIFY_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
VERIFY_MODEL="${BEDROCK_MODEL_ID:-}"
if [[ -z "$VERIFY_REGION" || -z "$VERIFY_MODEL" ]]; then
  echo "Usage: AWS_REGION=<region> BEDROCK_MODEL_ID=<model-id> $0" >&2
  exit 2
fi

VERIFY_TMP="$(mktemp -d)"
trap 'rm -rf "$VERIFY_TMP"' EXIT

echo "Region: $VERIFY_REGION"
CALLER_ARN="$(aws sts get-caller-identity --region "$VERIFY_REGION" --query Arn --output text)"
echo "Caller identity: verified ($CALLER_ARN)"

TEXTRACT_RESULT="$(aws textract get-document-analysis --region "$VERIFY_REGION" --job-id 0000000000000000000000000000000000000000000000000000000000000000 2>&1 || true)"
case "$TEXTRACT_RESULT" in
  *InvalidJobIdException*)
    echo "Textract GetDocumentAnalysis: reachable; start/extraction permissions remain unverified."
    ;;
  *AccessDenied*|*Unauthorized*)
    echo "Textract: DENIED" >&2
    exit 3
    ;;
  *)
    echo "Textract: UNVERIFIED (unexpected response; check region, network and credentials)." >&2
    exit 3
    ;;
esac

aws bedrock-runtime converse --region "$VERIFY_REGION" --model-id "$VERIFY_MODEL" \
  --messages '[{"role":"user","content":[{"text":"Return only the word OK."}]}]' \
  --inference-config '{"maxTokens":8,"temperature":0}' --output json > "$VERIFY_TMP/response.json"
echo "Bedrock model invocation: verified"

echo "UNVERIFIED: S3, DynamoDB, Step Functions, Cognito, and Textract StartDocumentAnalysis permissions require deployed integration tests."
echo "Template validation is not proof of data-plane permissions. Run 'sam validate --lint' before deployment."
