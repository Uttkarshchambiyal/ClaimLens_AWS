# ClaimLens architecture

## Request flow

1. Cognito issues a reviewer ID token containing an administrator-assigned, immutable `custom:tenant_id`.
2. API Gateway validates the token. The API Lambda derives tenancy only from the validated claim, never from the request body.
3. The UI creates a claim, requests a short-lived presigned POST per document, uploads directly to a private versioned S3 bucket under an S3-enforced content-type/encryption/size policy, and starts an analysis with an idempotency key.
4. Step Functions Standard returns control immediately and processes documents asynchronously. Each document worker reuses a recorded Textract job ID on retry.
5. Textract output is preserved in S3. Normalized fields in DynamoDB keep a document version, page, block IDs, normalized geometry, confidence, and excerpt.
6. Deterministic rules run first. Bedrock receives only a bounded evidence bundle with opaque citations and no tools or browsing. Its JSON response is rejected if its exact schema, enum values, or citations are invalid.
7. Reviewers inspect findings and evidence, annotate extraction corrections without overwriting raw extraction, record a disposition, and export a JSON report identifying its analysis version. Mutations record the authenticated Cognito subject, and disposition changes create append-only audit events. Corrections do not yet rerun automated checks; the report states this explicitly.

## Records

The single DynamoDB table uses `TENANT#<tenant>` as its partition key and a typed sort key. Claims, document versions, analyses, analysis snapshots, corrections, current reviewer dispositions, append-only review events, invoice fingerprints, and idempotency responses remain separate records. This makes tenant authorization part of every primary-key lookup. Idempotent requests acquire a conditional lease before running a producer; active duplicates return 409, and successful responses are cached.

Document bytes and complete Textract responses live under tenant/claim/document/version prefixes in S3. The analysis pins the uploaded S3 VersionId before starting extraction. Bucket versioning and DynamoDB point-in-time recovery are defined in SAM. `RetentionDays` expires current/noncurrent S3 data and assigns DynamoDB TTL timestamps; `LogRetentionDays` controls Lambda log groups. TTL deletion is asynchronous. These infrastructure settings have been statically validated, not deployed or verified against AWS.

## Trust boundaries

- Uploaded text is data, not an instruction channel.
- Model temperature is zero and input is limited to selected evidence. No agent, tools, browsing, write capability, or direct datastore access is exposed to the model.
- `PASS`, `FINDING`, `INSUFFICIENT_EVIDENCE`, `NOT_APPLICABLE`, and `ERROR` are independent of review priority.
- Extraction quality and evidence coverage are calculated and displayed separately.
- Missing support creates a request for evidence. It is never converted into a statement that care did not occur.
- Model or extraction failure produces a warning/error outcome and cannot silently become a clean result.

## Configurable assumptions

- `MoneyTolerancePaise` controls arithmetic tolerance; the default is ₹1.00.
- `RoundingMode` is `HALF_UP` or `HALF_EVEN` and is used during normalization to integer paise.
- `StayDayAllowance` controls how far a procedure date may fall outside admission/discharge boundaries.
- Invoice total, amount paid, balance due, and claimed amount have distinct normalized field names.
- `BedrockModelId` is a deployment parameter because regional model access differs.
- `DateOrder` defaults to `ISO_ONLY`; non-ISO numeric dates need explicit `DMY` or `MDY` configuration.

## Bounded extraction and failure behavior

Raw and normalized extraction are archived in S3. The inline document record is limited to 120 normalized fields and 160,000 serialized bytes; larger extractions produce a visible failure instead of an incomplete clean result. Combined analysis fields are bounded to 220,000 bytes. These prototype bounds do not replace deployment/load tests against AWS quotas.

Discharge/report prose includes at most 40 source-cited lines, capped at 240 characters each. Billed procedure descriptions retain source blocks for bounded semantic comparison. This is not a complete clinical-record analysis. Partial Textract results are labeled `PARTIAL` and excluded from automatic complete-packet checks. Completed workers skip repeated extraction/model calls; existing analysis snapshots win during interrupted-write recovery.
