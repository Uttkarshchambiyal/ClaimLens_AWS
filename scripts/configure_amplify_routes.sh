#!/usr/bin/env bash
set -euo pipefail

: "${AMPLIFY_APP_ID:?Set AMPLIFY_APP_ID to the ClaimLens Amplify app ID}"
CLAIMLENS_AWS_REGION="${CLAIMLENS_AWS_REGION:-ap-south-1}"

aws amplify update-app \
  --app-id "$AMPLIFY_APP_ID" \
  --region "$CLAIMLENS_AWS_REGION" \
  --custom-rules '[{"source":"/review","target":"/index.html","status":"200"},{"source":"/auth/login","target":"/index.html","status":"200"},{"source":"/auth/login/","target":"/index.html","status":"200"},{"source":"/auth/signup","target":"/index.html","status":"200"},{"source":"/auth/signup/","target":"/index.html","status":"200"},{"source":"/auth/callback","target":"/index.html","status":"200"},{"source":"/<*>","target":"/index.html","status":"404-200"}]' \
  --query 'app.customRules' \
  --output json
