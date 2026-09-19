#!/usr/bin/env bash
# Deploy the ClaimLens frontend to S3 and invalidate CloudFront cache.
#
# Usage:
#   ./scripts/deploy_frontend.sh <stack-name> [region]
#
# Example:
#   ./scripts/deploy_frontend.sh claimlens ap-south-1
#
# Prerequisites:
#   - AWS CLI configured with valid credentials
#   - Backend stack already deployed via `sam deploy`
#   - frontend/.env configured with production values

set -euo pipefail

STACK_NAME="${1:?Usage: deploy_frontend.sh <stack-name> [region]}"
REGION="${2:-${AWS_REGION:-ap-south-1}}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "━━━ ClaimLens Frontend Deploy ━━━"
echo "Stack:  $STACK_NAME"
echo "Region: $REGION"
echo ""

# Step 1: Fetch stack outputs
echo "→ Fetching stack outputs..."
OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

get_output() {
  echo "$OUTPUTS" | python3 -c "
import json, sys
outputs = json.load(sys.stdin)
for o in outputs:
    if o['OutputKey'] == '$1':
        print(o['OutputValue'])
        break
"
}

API_URL=$(get_output ApiUrl)
USER_POOL_ID=$(get_output UserPoolId)
CLIENT_ID=$(get_output UserPoolClientId)
COGNITO_DOMAIN=$(get_output CognitoDomain)
FRONTEND_BUCKET=$(get_output FrontendBucketName)
FRONTEND_URL=$(get_output FrontendUrl)

if [ -z "$FRONTEND_BUCKET" ] || [ -z "$FRONTEND_URL" ]; then
  echo "ERROR: FrontendBucket or FrontendUrl not found in stack outputs."
  echo "       Make sure you deployed the latest template with CloudFront resources."
  exit 1
fi

COGNITO_AUTHORITY="https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}"

echo "  API URL:        $API_URL"
echo "  Cognito:        $COGNITO_AUTHORITY"
echo "  Frontend URL:   $FRONTEND_URL"
echo "  Frontend Bucket: $FRONTEND_BUCKET"
echo ""

# Step 2: Write production .env
echo "→ Writing frontend/.env for production..."
cat > "$FRONTEND_DIR/.env" <<EOF
VITE_APP_MODE=production
VITE_API_BASE_URL=${API_URL}
VITE_COGNITO_AUTHORITY=${COGNITO_AUTHORITY}
VITE_COGNITO_CLIENT_ID=${CLIENT_ID}
VITE_COGNITO_REDIRECT_URI=${FRONTEND_URL}/auth/callback
VITE_COGNITO_LOGOUT_URI=${FRONTEND_URL}/
VITE_COGNITO_DOMAIN=${COGNITO_DOMAIN}
VITE_TENANT_CLAIM=custom:tenant_id
EOF
echo "  Wrote $FRONTEND_DIR/.env"
echo ""

# Step 3: Build
echo "→ Building frontend for production..."
cd "$FRONTEND_DIR"
npm ci --silent
npm run build
echo ""

# Step 4: Sync to S3
echo "→ Syncing dist/ to s3://${FRONTEND_BUCKET}..."
aws s3 sync dist/ "s3://${FRONTEND_BUCKET}/" \
  --region "$REGION" \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html" \
  --exclude "*.json"

# index.html and manifests should not be cached aggressively
aws s3 cp dist/index.html "s3://${FRONTEND_BUCKET}/index.html" \
  --region "$REGION" \
  --cache-control "no-cache, no-store, must-revalidate" \
  --content-type "text/html"

# Sync any JSON files (manifests etc.) with short cache
aws s3 sync dist/ "s3://${FRONTEND_BUCKET}/" \
  --region "$REGION" \
  --exclude "*" \
  --include "*.json" \
  --cache-control "public, max-age=60"

echo ""

# Step 5: Invalidate CloudFront cache
echo "→ Invalidating CloudFront cache..."
DISTRIBUTION_ID=$(aws cloudformation describe-stack-resource \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --logical-resource-id FrontendDistribution \
  --query 'StackResourceDetail.PhysicalResourceId' \
  --output text)

INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths "/*" \
  --query 'Invalidation.Id' \
  --output text)

echo "  Distribution:  $DISTRIBUTION_ID"
echo "  Invalidation:  $INVALIDATION_ID"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Frontend deployed!"
echo ""
echo "   $FRONTEND_URL"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
