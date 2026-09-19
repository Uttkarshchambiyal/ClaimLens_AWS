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
| Rule precision/recall | `scripts/evaluate_quality.py`; zero false-clean gate | Re-run against expanded labeled corpus |
| Maximum packet shape | `scripts/benchmark_large_packet.py`; 10 documents/120 fields | Deployed load and quota test pending |
| OCR layout corpus | Eight-page generated PDF plus ground truth | Live Textract metrics pending |
| Bedrock consistency | Strict local schema/citation tests | Repeated live comparison pending |

## Current local results

- 65 Python tests pass, including Moto-emulated S3/DynamoDB integration, expanded extraction/quality tests and stubbed worker tests. These check version pinning, duplicate analysis requests, reviewer attribution/audit events, retention timestamps, report content, cross-tenant denial, Textract pagination/retries, partial extraction, low-confidence gating, repeated headers, explicit adjustments, Hindi labels, numeric-date ambiguity, malformed money, missing geometry, bounded prose and snapshot recovery. They do not call live Textract or Bedrock.
- 14 React interaction tests pass, including hero navigation/sample preview, animation pause, reviewer filters, queue selection, URL restoration, keyboard tabs, document-to-evidence navigation, corrections and save-error retry, dispositions, mock upload validation/idempotency, the upload dialog, and report-download initiation. These use jsdom, not a real browser.
- TypeScript compilation, Vite production build, frontend formatting, CloudFormation/SAM lint (`cfn-lint`), and verifier shell syntax pass.
- Playwright exercises the current mock landing, queue, claim review, disposition mutation, audit activity, evidence viewer, and upload dialog in Chromium at 1536x960 and 390x844. It also checks page errors, console errors, duplicate DOM IDs, image alt text, and viewport-level overflow. Six current screenshots were manually inspected; production authentication and signed-source rendering remain unverified.
- Current full `npm audit` and `pip-audit` checks report no known dependency vulnerabilities. This is not a penetration test and advisory results can change.
- AWS CLI and SAM CLI are installed. No credentials or deployed stack are available yet, so no live AWS identity, permissions, extraction, model invocation, or deployment has been verified.

The verifier performs identity/region checks, a Textract GetDocumentAnalysis reachability probe, and a minimal synthetic Bedrock Converse invocation. The invocation may incur usage charges. It does not create infrastructure, and it does not establish all required data-plane permissions. A frontend build, local mock run, or Moto test does not count as AWS verification.

## Remaining acceptance work

The current reproducible report is `docs/verification-results.json`. Run `.venv/bin/python scripts/verify_project.py` to refresh all local gates. The 14-page project guide is `output/pdf/claimlens-architecture-and-readiness.pdf`; all rendered pages were inspected for layout. The supplied GitHub Actions workflow has not yet run on GitHub.

- Provision tenant-assigned Cognito users and verify real authentication, refresh, logout, and cross-tenant HTTP access.
- Exercise presigned S3 upload/read, version pinning, Textract pagination/partial failures, Step Functions retries, and strict Bedrock output handling in the chosen AWS region.
- Verify source overlays against original synthetic PDF/image pages through deployed signed S3 URLs, plus Cognito flows and keyboard-only acceptance on the production host.
- Run `scripts/evaluate_live_aws.py` on the included synthetic OCR corpus and record field precision/recall for clear, repeated-header, adjustment, multilingual, rotated, blurred and handwritten-style pages.
- Run `scripts/run_live_acceptance.py` after deployment; it automates temporary-user auth, tenant denial, signed upload/viewing, workflow inspection, deliberate malformed-PDF handling, strict Bedrock acceptance, report retrieval and source-coordinate validation without storing secrets.
- Implement correction-driven reanalysis/version progression before treating corrections as authoritative results.
- Add load, resource-size, IAM, deployed retention/TTL, and deployment recovery tests before any production medical data is considered.

## Expanded evaluation evidence

- Explicit tax/GST, discount and signed round-off arithmetic is implemented and regression tested.
- Repeated table headers are ignored, and broader medical abbreviations can trigger support review.
- Printed Hindi labels are mapped when Textract returns them; no unsupported language is silently translated or guessed.
- A configurable minimum OCR confidence prevents low-quality fields from producing a clean result.
- The local benchmark reports status accuracy, finding precision/recall/F1, a confusion matrix and unsafe false-clean count.
- The maximum-shape local benchmark measures ten documents, 120 fields and the configured serialized payload bound.
- These controls reduce unsafe conclusions; only the live evaluator can establish Textract and Bedrock performance in the selected AWS region.
