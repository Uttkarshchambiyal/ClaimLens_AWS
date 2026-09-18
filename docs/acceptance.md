# Acceptance and verification matrix

| Capability | Automated check | Cloud verification |
|---|---|---|
| Bill arithmetic and explicit tolerance | `test_money_and_rules.py` | Pending AWS deployment |
| Ambiguous normalization does not pass | `test_ambiguous_comma_is_not_silently_normalized` | Local logic |
| Evidence references and model citations | `test_evidence_and_semantic.py` | Bedrock invocation pending |
| Tenant isolation | `test_tenant_isolation_blocks_cross_tenant_claim_access` | API authorizer pending |
| Duplicate requests/workers | `test_duplicate_*`; recorded Textract job reuse | Step Functions retry pending |
| Partial failure is not clean | `test_partial_failure_never_becomes_clean` | Textract failure injection pending |
| Upload-to-review flow | `test_complete_local_upload_to_review_flow` | S3/API/Step Functions pending |
| Consistent packet | synthetic `consistent.json` plus rule suite | Pending |
| Inconsistent packet | synthetic `inconsistent.json` plus mismatch tests | Pending |
| Ambiguous packet | synthetic `ambiguous.json` plus normalization tests | Pending |
| Legitimate edge case | synthetic `legitimate-edge.json` | Pending |
| Reviewer attribution and audit history | authenticated subject plus append-only `REVIEW_EVENT` integration test | Cognito identity pending |
| Retention controls | repository expiry tests plus SAM lint | Deployed lifecycle/TTL observation pending |
| Responsive browser workflow | Playwright desktop/mobile navigation, mutation, evidence and dialog flow | Production host pending |

## Current local results

- 59 Python tests pass, including Moto-emulated S3/DynamoDB integration and stubbed worker tests. These check version pinning, duplicate analysis requests, reviewer attribution/audit events, retention timestamps, report content, cross-tenant denial, Textract pagination/retries, partial extraction, numeric-date ambiguity, malformed money, missing geometry, bounded prose and snapshot recovery. They do not call live Textract or Bedrock.
- 14 React interaction tests pass, including hero navigation/sample preview, animation pause, reviewer filters, queue selection, URL restoration, keyboard tabs, document-to-evidence navigation, corrections and save-error retry, dispositions, mock upload validation/idempotency, the upload dialog, and report-download initiation. These use jsdom, not a real browser.
- TypeScript compilation, Vite production build, frontend formatting, CloudFormation/SAM lint (`cfn-lint`), and verifier shell syntax pass.
- Playwright exercises the current mock landing, queue, claim review, disposition mutation, audit activity, evidence viewer, and upload dialog in Chromium at 1536x960 and 390x844. It also checks page errors, console errors, duplicate DOM IDs, image alt text, and viewport-level overflow. Four current screenshots were manually inspected; production authentication and signed-source rendering remain unverified.
- Current full `npm audit` and `pip-audit` checks report no known dependency vulnerabilities. This is not a penetration test and advisory results can change.
- `scripts/verify_aws.sh` currently reports **AWS CLI is not installed**. No live AWS identity, region, permissions, extraction, model invocation, or deployment was verified.

The verifier performs identity/region checks, a Textract GetDocumentAnalysis reachability probe, and a minimal synthetic Bedrock Converse invocation. The invocation may incur usage charges. It does not create infrastructure, and it does not establish all required data-plane permissions. A frontend build, local mock run, or Moto test does not count as AWS verification.

## Remaining acceptance work

The current reproducible report is `docs/verification-results.json`. Run `.venv/bin/python scripts/verify_project.py` to refresh all local gates. The 14-page project guide is `output/pdf/claimlens-architecture-and-readiness.pdf`; all rendered pages were inspected for layout. The supplied GitHub Actions workflow has not yet run on GitHub.

- Provision tenant-assigned Cognito users and verify real authentication, refresh, logout, and cross-tenant HTTP access.
- Exercise presigned S3 upload/read, version pinning, Textract pagination/partial failures, Step Functions retries, and strict Bedrock output handling in the chosen AWS region.
- Verify source overlays against original synthetic PDF/image pages through deployed signed S3 URLs, plus Cognito flows and keyboard-only acceptance on the production host.
- Evaluate Textract normalization on more hospital-table layouts, tax/discount adjustments, ambiguous totals and date formats. Existing synthetic tests are not an OCR accuracy benchmark.
- Implement correction-driven reanalysis/version progression before treating corrections as authoritative results.
- Add load, resource-size, IAM, deployed retention/TTL, and deployment recovery tests before any production medical data is considered.
