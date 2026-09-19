# ClaimLens evaluation protocol

ClaimLens separates three kinds of evidence so a passing local test is never presented as live OCR accuracy.

## 1. Deterministic rule benchmark

Run:

```bash
.venv/bin/python scripts/evaluate_quality.py
```

This evaluates every labeled normalized-field packet in `synthetic/` and writes `docs/quality-benchmark-results.json`. It reports exact status accuracy, finding precision, finding recall, F1, a status confusion matrix, and the number of unsafe false-clean results.

This benchmark verifies Python rule behavior only. It does not measure Textract or Bedrock.

## 2. Maximum-shape local benchmark

Run:

```bash
.venv/bin/python scripts/benchmark_large_packet.py
```

The benchmark exercises the supported boundary of ten documents and 120 source-cited fields, records serialized input size and local evaluation time, and fails if the configured 220,000-byte combined-field bound is exceeded. It writes `docs/large-packet-benchmark.json`.

This is not an AWS load test. Deployed concurrency, Lambda memory/duration, Step Functions history, Textract quotas and DynamoDB throttling still require cloud measurements.

## 3. Live OCR and model benchmark

The visually inspected eight-page synthetic benchmark is `output/pdf/claimlens-evaluation-benchmark.pdf`. Its ground truth is `benchmarks/evaluation-ground-truth.json`. It covers:

- clear digital forms and tables;
- a repeated table header on a continuation page;
- GST, discount and signed round-off values;
- printed Hindi-English labels;
- medical abbreviations and terminology variants;
- a rotated scan;
- a blurred, low-contrast scan;
- a handwritten-style bitmap.

With AWS credentials, an existing private versioned bucket and an enabled Bedrock model, run:

```bash
.venv/bin/python scripts/evaluate_live_aws.py \
  --bucket <private-benchmark-bucket> \
  --region <aws-region> \
  --model-id <bedrock-model-id> \
  --bedrock-runs 5 \
  --cleanup
```

The script uploads only the synthetic benchmark, runs asynchronous Textract `FORMS` and `TABLES` analysis, follows every pagination token, applies the production adapter and confidence gate, computes field precision/recall/F1 against ground truth, and repeats the bounded Bedrock comparison to measure valid-output rate and exact-output consistency. It writes `docs/live-evaluation-results.json`.

The live script makes paid AWS calls. It creates no infrastructure. `--cleanup` removes the uploaded benchmark object version after the report is written.

## Interpretation

- Low-confidence fields remain visible but receive `LOW_CONFIDENCE`; deterministic checks cannot convert them into `PASS`.
- A false-clean result means the expected status was `FINDING`, `INSUFFICIENT_EVIDENCE` or `ERROR`, while the observed status was `PASS`. The local quality gate requires zero false-clean results.
- Perfect synthetic metrics show regression correctness for labeled cases, not clinical validity or generalization to every hospital layout.
- A live report is required before stating Textract accuracy, Bedrock consistency or production performance.
- Use only fictional patients and providers. This protocol is not approval to process protected health information.
