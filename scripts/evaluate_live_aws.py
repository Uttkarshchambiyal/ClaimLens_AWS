#!/usr/bin/env python3
"""Measure live Textract extraction and Bedrock output consistency.

This script makes paid AWS API calls and uploads only the included synthetic
benchmark to an existing private bucket. It creates no infrastructure and
never writes AWS account IDs, credentials, prompts, or model output text to
the report.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from claimlens.config import Settings
from claimlens.extraction import fields_from_adapter
from claimlens.quality import field_metrics
from claimlens.semantic import BedrockAdapter, validate_model_output
from claimlens.workflow import _adapter_fields


def textract_pages(client, job_id: str, timeout_seconds: int) -> tuple[str, list[dict]]:
    """Wait for a Textract job and exhaust every response pagination token."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        first = client.get_document_analysis(JobId=job_id)
        status = first["JobStatus"]
        if status == "IN_PROGRESS":
            time.sleep(5)
            continue
        if status not in {"SUCCEEDED", "PARTIAL_SUCCESS"}:
            return status, [first]
        pages = [first]
        token = first.get("NextToken")
        while token:
            page = client.get_document_analysis(JobId=job_id, NextToken=token)
            pages.append(page)
            token = page.get("NextToken")
        return status, pages
    raise TimeoutError(f"Textract did not finish within {timeout_seconds} seconds")


def _session(boto3, profile: str | None, region: str):
    kwargs = {"region_name": region}
    if profile:
        kwargs["profile_name"] = profile
    return boto3.session.Session(**kwargs)


def _bucket_controls(s3, bucket: str) -> dict:
    encryption = s3.get_bucket_encryption(Bucket=bucket)
    algorithms = sorted({
        row["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
        for row in encryption["ServerSideEncryptionConfiguration"]["Rules"]
    })
    public = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
    versioning = s3.get_bucket_versioning(Bucket=bucket).get("Status")
    return {
        "versioningEnabled": versioning == "Enabled",
        "encryptionAlgorithms": algorithms,
        "allPublicAccessBlocked": all(public.get(key) is True for key in (
            "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"
        )),
    }


def _difference(expected: list[dict], actual: list[dict]) -> tuple[list[dict], list[dict]]:
    def key(item: dict) -> tuple[str, int, str]:
        return (
            str(item.get("name", "")),
            int(item.get("page", 1)),
            json.dumps(item.get("normalizedValue"), sort_keys=True, ensure_ascii=False),
        )

    expected_by_key = {key(item): item for item in expected}
    actual_by_key = {key(item): item for item in actual}
    return (
        [expected_by_key[item] for item in sorted(expected_by_key.keys() - actual_by_key.keys())],
        [actual_by_key[item] for item in sorted(actual_by_key.keys() - expected_by_key.keys())],
    )


def _validate_ground_truth(payload: dict) -> tuple[list[str], list[dict]]:
    categories = payload.get("categories")
    expected = payload.get("expectedFields")
    if not isinstance(categories, list) or not categories or not all(isinstance(value, str) for value in categories):
        raise ValueError("Ground truth must contain a non-empty categories array")
    if not isinstance(expected, list) or not expected:
        raise ValueError("Ground truth must contain expectedFields")
    if any(not isinstance(item, dict) or not {"name", "page", "normalizedValue"} <= set(item) for item in expected):
        raise ValueError("Every expected field needs name, page, and normalizedValue")
    pages = {int(item["page"]) for item in expected}
    if pages - set(range(1, len(categories) + 1)):
        raise ValueError("Ground-truth page numbers do not map to categories")
    return categories, expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True, help="Existing private, encrypted, versioned S3 bucket")
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile", help="Optional AWS shared-config profile")
    parser.add_argument("--document", type=Path, default=ROOT / "output/pdf/claimlens-evaluation-benchmark.pdf")
    parser.add_argument("--ground-truth", type=Path, default=ROOT / "benchmarks/evaluation-ground-truth.json")
    parser.add_argument("--model-id", help="Optional Bedrock model ID for repeated consistency checks")
    parser.add_argument("--bedrock-runs", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--min-precision", type=float, default=0.0)
    parser.add_argument("--min-recall", type=float, default=0.0)
    parser.add_argument("--min-valid-model-rate", type=float, default=1.0)
    parser.add_argument("--cleanup", action="store_true", help="Delete the uploaded benchmark object version")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/live-evaluation-results.json")
    args = parser.parse_args()
    if not args.document.is_file():
        raise SystemExit(f"Benchmark document not found: {args.document}")
    if not args.ground_truth.is_file():
        raise SystemExit(f"Ground truth not found: {args.ground_truth}")
    if not 1 <= args.bedrock_runs <= 20:
        raise SystemExit("--bedrock-runs must be between 1 and 20")
    for name, value in (("--min-precision", args.min_precision), ("--min-recall", args.min_recall), ("--min-valid-model-rate", args.min_valid_model_rate)):
        if not 0 <= value <= 1:
            raise SystemExit(f"{name} must be between 0 and 1")

    truth = json.loads(args.ground_truth.read_text())
    categories, expected = _validate_ground_truth(truth)

    import boto3

    session = _session(boto3, args.profile, args.region)
    # Authentication preflight only. Discard the account ID so reports are safe to share.
    identity = session.client("sts").get_caller_identity()
    if not identity.get("Arn"):
        raise RuntimeError("AWS identity preflight did not return an ARN")
    s3 = session.client("s3")
    controls = _bucket_controls(s3, args.bucket)
    if not all((controls["versioningEnabled"], controls["allPublicAccessBlocked"], controls["encryptionAlgorithms"])):
        raise RuntimeError("Benchmark bucket must be encrypted, versioned, and block all public access")

    textract = session.client("textract")
    document_bytes = args.document.read_bytes()
    key = f"claimlens-benchmarks/{uuid.uuid4()}/{args.document.name}"
    upload = s3.put_object(
        Bucket=args.bucket, Key=key, Body=document_bytes,
        ContentType="application/pdf", ServerSideEncryption="AES256",
    )
    started_at = time.monotonic()
    try:
        source = {"Bucket": args.bucket, "Name": key}
        if upload.get("VersionId"):
            source["Version"] = upload["VersionId"]
        started = textract.start_document_analysis(
            DocumentLocation={"S3Object": source},
            FeatureTypes=["FORMS", "TABLES"],
            ClientRequestToken=uuid.uuid4().hex,
            JobTag="claimlens-quality-benchmark",
        )
        status, response_pages = textract_pages(textract, started["JobId"], args.timeout)
        elapsed = round(time.monotonic() - started_at, 3)
        blocks = [block for response in response_pages for block in response.get("Blocks", [])]
        settings = Settings(aws_region=args.region, date_order="DMY")
        fields, evidence = fields_from_adapter("benchmark", 1, _adapter_fields(blocks, "BILL"), settings)
        actual = [{
            "name": field.name, "page": field.evidence.page,
            "normalizedValue": field.normalized_value,
            "normalizationStatus": field.normalization_status,
            "confidence": field.evidence.confidence,
        } for field in fields]
        extraction_metrics = field_metrics(expected, actual)
        missed, unexpected = _difference(expected, actual)
        category_metrics = {}
        for page_number, category in enumerate(categories, start=1):
            category_metrics[category] = field_metrics(
                [item for item in expected if int(item["page"]) == page_number],
                [item for item in actual if int(item["page"]) == page_number],
            )

        bedrock = {
            "requested": bool(args.model_id), "modelId": args.model_id,
            "runs": 0, "validRuns": 0, "validOutputRate": None,
            "exactMatchRate": None, "distinctValidOutputs": 0,
            "resultHashes": {}, "errors": {},
        }
        if args.model_id:
            adapter = BedrockAdapter(args.model_id, session.client("bedrock-runtime"))
            bundle = [{
                "evidenceId": field.evidence.evidence_id, "documentType": "BILL",
                "field": field.name, "value": field.normalized_value,
                "excerpt": field.evidence.excerpt,
            } for field in fields]
            hashes: Counter[str] = Counter()
            errors: Counter[str] = Counter()
            for _ in range(args.bedrock_runs):
                bedrock["runs"] += 1
                try:
                    payload = adapter.compare(bundle)
                    validate_model_output(payload, evidence)
                    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                    hashes[sha256(canonical.encode()).hexdigest()] += 1
                    bedrock["validRuns"] += 1
                except Exception as exc:
                    errors[type(exc).__name__] += 1
            bedrock["validOutputRate"] = round(bedrock["validRuns"] / args.bedrock_runs, 4)
            bedrock["exactMatchRate"] = round(max(hashes.values(), default=0) / args.bedrock_runs, 4)
            bedrock["distinctValidOutputs"] = len(hashes)
            bedrock["resultHashes"] = dict(hashes.most_common())
            bedrock["errors"] = dict(errors.most_common())

        gates = {
            "textractCompleted": status in {"SUCCEEDED", "PARTIAL_SUCCESS"},
            "precisionThresholdMet": extraction_metrics["precision"] >= args.min_precision,
            "recallThresholdMet": extraction_metrics["recall"] >= args.min_recall,
            "bedrockValidRateMet": not args.model_id or bedrock["validOutputRate"] >= args.min_valid_model_rate,
        }
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "scope": "Live AWS synthetic benchmark; not authorization for real patient data.",
            "region": args.region,
            "authenticated": True,
            "document": {
                "name": args.document.name, "sha256": sha256(document_bytes).hexdigest(),
                "bytes": len(document_bytes), "expectedPages": len(categories),
            },
            "bucketControls": controls,
            "textract": {
                "status": status, "elapsedSeconds": elapsed,
                "responsePages": len(response_pages), "paginationObserved": len(response_pages) > 1,
                "documentPages": max((int(row.get("DocumentMetadata", {}).get("Pages", 0)) for row in response_pages), default=0),
                "blocks": len(blocks),
            },
            "extraction": extraction_metrics,
            "categoryMetrics": category_metrics,
            "missedExpectedFields": missed,
            "unexpectedFields": unexpected,
            "actualFields": actual,
            "bedrockConsistency": bedrock,
            "gates": gates,
            "ready": all(gates.values()),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({
            "output": str(args.output), "textract": report["textract"],
            "extraction": extraction_metrics, "bedrockConsistency": bedrock, "gates": gates,
        }, indent=2))
        return 0 if report["ready"] else 1
    finally:
        if args.cleanup:
            kwargs = {"Bucket": args.bucket, "Key": key}
            if upload.get("VersionId"):
                kwargs["VersionId"] = upload["VersionId"]
            s3.delete_object(**kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
