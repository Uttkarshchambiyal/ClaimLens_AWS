#!/usr/bin/env python3
"""Run ClaimLens end-to-end acceptance against a deployed SAM stack.

The runner creates two short-lived synthetic Cognito reviewers, exercises the
real HTTP API and presigned S3 URLs, and deletes the users on exit. It writes a
sanitized JSON report and optional source-overlay PNG. It never records tokens,
passwords, account IDs, document text, or user email addresses.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import secrets
import string
import sys
import time
import uuid
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TERMINAL_ANALYSIS = {"COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED"}


def _session(boto3, profile: str | None, region: str):
    kwargs = {"region_name": region}
    if profile:
        kwargs["profile_name"] = profile
    return boto3.session.Session(**kwargs)


def _password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#%+="
    # Required classes are inserted explicitly before shuffling.
    chars = list("Aa1!" + "".join(secrets.choice(alphabet) for _ in range(24)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def _stack_outputs(cloudformation, stack_name: str) -> dict[str, str]:
    stacks = cloudformation.describe_stacks(StackName=stack_name)["Stacks"]
    if len(stacks) != 1 or stacks[0]["StackStatus"].endswith("IN_PROGRESS"):
        raise RuntimeError("The CloudFormation stack is not in a stable state")
    outputs = {row["OutputKey"]: row["OutputValue"] for row in stacks[0].get("Outputs", [])}
    required = {
        "ApiUrl", "UserPoolId", "UserPoolClientId", "DocumentsBucketName",
        "RecordsTableName", "AnalysisStateMachineArn", "CognitoDomain",
    }
    missing = sorted(required - outputs.keys())
    if missing:
        raise RuntimeError("Missing stack outputs: " + ", ".join(missing))
    return outputs


def retry_policy_evidence(definition: dict[str, Any]) -> dict[str, Any]:
    """Return evidence for the three Lambda service-retry policies."""
    outer = definition.get("States", {})
    processor = outer.get("ExtractDocuments", {}).get("ItemProcessor", {}).get("States", {})
    states = {
        "StartExtraction": processor.get("StartExtraction", {}),
        "PollExtraction": processor.get("PollExtraction", {}),
        "Analyze": outer.get("Analyze", {}),
    }
    result = {}
    required_errors = {
        "Lambda.ServiceException", "Lambda.AWSLambdaException",
        "Lambda.SdkClientException", "Lambda.TooManyRequestsException",
    }
    for name, state in states.items():
        policies = state.get("Retry", [])
        matching = next((row for row in policies if required_errors <= set(row.get("ErrorEquals", []))), None)
        result[name] = {
            "configured": bool(matching),
            "maxAttempts": int(matching.get("MaxAttempts", 0)) if matching else 0,
            "intervalSeconds": int(matching.get("IntervalSeconds", 0)) if matching else 0,
            "backoffRate": float(matching.get("BackoffRate", 0)) if matching else 0,
        }
        result[name]["valid"] = (
            result[name]["configured"] and result[name]["maxAttempts"] >= 3
            and result[name]["intervalSeconds"] >= 1 and result[name]["backoffRate"] > 1
        )
    return result


def _create_user(cognito, pool_id: str, client_id: str, tenant: str) -> dict[str, str]:
    suffix = uuid.uuid4().hex
    username = f"claimlens-live-{suffix}@example.invalid"
    password = _password()
    cognito.admin_create_user(
        UserPoolId=pool_id,
        Username=username,
        UserAttributes=[
            {"Name": "email", "Value": username},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "custom:tenant_id", "Value": tenant},
            {"Name": "name", "Value": "Synthetic acceptance reviewer"},
        ],
        MessageAction="SUPPRESS",
    )
    cognito.admin_set_user_password(
        UserPoolId=pool_id, Username=username, Password=password, Permanent=True,
    )
    auth = cognito.admin_initiate_auth(
        UserPoolId=pool_id,
        ClientId=client_id,
        AuthFlow="ADMIN_USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )["AuthenticationResult"]
    return {
        "username": username,
        "idToken": auth["IdToken"],
        "accessToken": auth["AccessToken"],
        "refreshToken": auth["RefreshToken"],
    }


def _refresh_user(cognito, client_id: str, refresh_token: str) -> dict[str, str]:
    result = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="REFRESH_TOKEN_AUTH",
        AuthParameters={"REFRESH_TOKEN": refresh_token},
    )["AuthenticationResult"]
    return {"idToken": result["IdToken"], "accessToken": result["AccessToken"]}


class Api:
    def __init__(self, requests_module, base_url: str, id_token: str):
        self.requests = requests_module
        self.base_url = base_url.rstrip("/")
        self.id_token = id_token

    def request(self, method: str, path: str, *, body: dict | None = None, idempotent: bool = False, expected: tuple[int, ...] = (200,)):
        headers = {"Authorization": f"Bearer {self.id_token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idempotent:
            headers["Idempotency-Key"] = uuid.uuid4().hex
        response = self.requests.request(
            method, self.base_url + path, headers=headers, json=body, timeout=30,
        )
        if response.status_code not in expected:
            error = response.text[:500].replace("\n", " ")
            raise RuntimeError(f"{method} {path} returned {response.status_code}: {error}")
        if not response.content:
            return None, response.status_code
        return response.json(), response.status_code


def _upload_document(api: Api, requests_module, document: Path, document_type: str = "BILL") -> tuple[str, str]:
    claim, _ = api.request("POST", "/claims", body={}, idempotent=True, expected=(201,))
    claim_id = claim["claimId"]
    registered, _ = api.request(
        "POST", f"/claims/{claim_id}/documents/upload-request",
        body={"filename": document.name, "contentType": "application/pdf", "documentType": document_type},
        idempotent=True, expected=(201,),
    )
    with document.open("rb") as handle:
        upload = requests_module.post(
            registered["uploadUrl"], data=registered["uploadFields"],
            files={"file": (document.name, handle, "application/pdf")}, timeout=90,
        )
    if upload.status_code not in {200, 201, 204}:
        raise RuntimeError(f"Presigned S3 upload returned {upload.status_code}")
    return claim_id, registered["documentId"]


def _start_analysis(api: Api, claim_id: str, document_id: str) -> str:
    payload, _ = api.request(
        "POST", "/analyses", body={"claimId": claim_id, "documentIds": [document_id]},
        idempotent=True, expected=(202,),
    )
    return payload["analysisId"]


def _wait_analysis(api: Api, analysis_id: str, timeout_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        payload, _ = api.request("GET", f"/analyses/{analysis_id}")
        if payload.get("status") in TERMINAL_ANALYSIS:
            return payload
        time.sleep(5)
    raise TimeoutError(f"Analysis {analysis_id} did not finish within {timeout_seconds} seconds")


def _find_execution(stepfunctions, state_machine_arn: str, analysis_id: str) -> dict:
    expected_name = analysis_id.replace("_", "-")[:80]
    token = None
    for _ in range(10):
        kwargs = {"stateMachineArn": state_machine_arn, "maxResults": 100}
        if token:
            kwargs["nextToken"] = token
        response = stepfunctions.list_executions(**kwargs)
        match = next((row for row in response.get("executions", []) if row["name"] == expected_name), None)
        if match:
            return match
        token = response.get("nextToken")
        if not token:
            break
    raise RuntimeError("Could not locate the Step Functions execution for the analysis")


def _execution_evidence(stepfunctions, execution_arn: str) -> dict:
    events = []
    token = None
    while True:
        kwargs = {"executionArn": execution_arn, "maxResults": 1000}
        if token:
            kwargs["nextToken"] = token
        response = stepfunctions.get_execution_history(**kwargs)
        events.extend(response.get("events", []))
        token = response.get("nextToken")
        if not token:
            break
    failures = Counter(
        row["type"] for row in events
        if row["type"].endswith("Failed") or row["type"].endswith("TimedOut")
    )
    return {"eventCount": len(events), "failureEvents": dict(sorted(failures.items()))}


def _textract_evidence(textract, job_id: str) -> dict:
    responses = []
    token = None
    while True:
        kwargs = {"JobId": job_id}
        if token:
            kwargs["NextToken"] = token
        response = textract.get_document_analysis(**kwargs)
        responses.append(response)
        token = response.get("NextToken")
        if not token:
            break
    return {
        "status": responses[0]["JobStatus"],
        "responsePages": len(responses),
        "paginationObserved": len(responses) > 1,
        "blocks": sum(len(row.get("Blocks", [])) for row in responses),
        "documentPages": int(responses[0].get("DocumentMetadata", {}).get("Pages", 0)),
    }


def validate_highlights(analysis: dict, pdf_bytes: bytes) -> tuple[dict, dict | None]:
    """Validate cited normalized geometry and return one overlay candidate."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for source-overlay acceptance") from exc
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    citations = [
        citation
        for finding in analysis.get("findings", [])
        for citation in finding.get("evidence", [])
    ]
    valid = 0
    first = None
    for citation in citations:
        geometry = citation.get("geometry", {})
        required = ("left", "top", "width", "height")
        if not all(isinstance(geometry.get(key), (int, float)) for key in required):
            continue
        left, top, width, height = (float(geometry[key]) for key in required)
        page = int(citation.get("page", 0))
        if not (1 <= page <= document.page_count and 0 <= left <= 1 and 0 <= top <= 1 and width > 0 and height > 0 and left + width <= 1.001 and top + height <= 1.001):
            continue
        valid += 1
        if first is None:
            first = {"page": page, "geometry": {key: float(geometry[key]) for key in required}}
    result = {
        "pdfPages": document.page_count,
        "citations": len(citations),
        "validGeometryCitations": valid,
        "allCitationGeometryValid": bool(citations) and valid == len(citations),
    }
    document.close()
    return result, first


def _write_overlay(pdf_bytes: bytes, candidate: dict, output: Path) -> None:
    import fitz
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = document[candidate["page"] - 1]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    image_document = fitz.open("png", pixmap.tobytes("png"))
    image_page = image_document[0]
    rect = image_page.rect
    box = candidate["geometry"]
    highlight = fitz.Rect(
        rect.width * box["left"], rect.height * box["top"],
        rect.width * (box["left"] + box["width"]),
        rect.height * (box["top"] + box["height"]),
    )
    image_page.draw_rect(highlight, color=(0.91, 0.25, 0.20), width=4)
    output.parent.mkdir(parents=True, exist_ok=True)
    image_page.get_pixmap(alpha=False).save(output)
    image_document.close()
    document.close()


def _logout_verified(cognito, access_token: str) -> bool:
    cognito.get_user(AccessToken=access_token)
    cognito.global_sign_out(AccessToken=access_token)
    try:
        cognito.get_user(AccessToken=access_token)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        return code in {"NotAuthorizedException", "UserNotFoundException"}
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", default="claimlens-hackathon")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile", help="Optional AWS shared-config profile")
    parser.add_argument("--document", type=Path, default=ROOT / "output/pdf/claimlens-evaluation-benchmark.pdf")
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--keep-users", action="store_true", help="Keep synthetic users after the test (passwords are still not saved)")
    parser.add_argument("--skip-failure-case", action="store_true", help="Skip the deliberately malformed synthetic PDF case")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/live-acceptance-results.json")
    parser.add_argument("--overlay", type=Path, default=ROOT / "docs/live-source-overlay-proof.png")
    args = parser.parse_args()
    if not args.document.is_file():
        raise SystemExit(f"Synthetic benchmark not found: {args.document}")

    import boto3
    import requests

    session = _session(boto3, args.profile, args.region)
    if not session.client("sts").get_caller_identity().get("Arn"):
        raise RuntimeError("AWS identity preflight failed")
    outputs = _stack_outputs(session.client("cloudformation"), args.stack)
    cognito = session.client("cognito-idp")
    stepfunctions = session.client("stepfunctions")
    dynamodb = session.resource("dynamodb").Table(outputs["RecordsTableName"])
    textract = session.client("textract")
    users: list[dict[str, str]] = []
    checks: dict[str, Any] = {}
    report: dict[str, Any] = {}
    started_at = time.monotonic()
    try:
        user_a = _create_user(cognito, outputs["UserPoolId"], outputs["UserPoolClientId"], "acceptance-a")
        users.append(user_a)
        user_b = _create_user(cognito, outputs["UserPoolId"], outputs["UserPoolClientId"], "acceptance-b")
        users.append(user_b)
        refreshed = _refresh_user(cognito, outputs["UserPoolClientId"], user_a["refreshToken"])
        checks["cognito"] = {
            "login": bool(user_a["idToken"] and user_b["idToken"]),
            "refresh": bool(refreshed["idToken"] and refreshed["idToken"] != user_a["idToken"]),
            "logout": False,
        }
        api_a = Api(requests, outputs["ApiUrl"], refreshed["idToken"])
        api_b = Api(requests, outputs["ApiUrl"], user_b["idToken"])

        claim_id, document_id = _upload_document(api_a, requests, args.document)
        _, isolation_status = api_b.request("GET", f"/claims/{claim_id}", expected=(403, 404))
        checks["tenantIsolation"] = {"crossTenantStatus": isolation_status, "blocked": isolation_status in {403, 404}}

        analysis_id = _start_analysis(api_a, claim_id, document_id)
        analysis = _wait_analysis(api_a, analysis_id, args.timeout)
        source, _ = api_a.request("GET", f"/claims/{claim_id}/documents/{document_id}")
        source_response = requests.get(source["downloadUrl"], timeout=90)
        source_response.raise_for_status()
        pdf_bytes = source_response.content
        original_bytes = args.document.read_bytes()
        checks["signedSource"] = {
            "contentType": source_response.headers.get("Content-Type", "").split(";")[0],
            "isPdf": pdf_bytes.startswith(b"%PDF"),
            "exactSourceMatch": sha256(pdf_bytes).digest() == sha256(original_bytes).digest(),
            "bytes": len(pdf_bytes),
        }
        highlights, candidate = validate_highlights(analysis, pdf_bytes)
        checks["sourceHighlighting"] = highlights
        if candidate:
            _write_overlay(pdf_bytes, candidate, args.overlay)
            checks["sourceHighlighting"]["proofImage"] = str(args.overlay.relative_to(ROOT))

        item = dynamodb.get_item(
            Key={"pk": "TENANT#acceptance-a", "sk": f"DOCUMENT#{document_id}"},
            ConsistentRead=True,
        ).get("Item", {})
        if not item.get("textractJobId"):
            raise RuntimeError("Deployed document record has no Textract job ID")
        checks["textract"] = _textract_evidence(textract, item["textractJobId"])

        definition = json.loads(stepfunctions.describe_state_machine(
            stateMachineArn=outputs["AnalysisStateMachineArn"]
        )["definition"])
        policies = retry_policy_evidence(definition)
        execution = _find_execution(stepfunctions, outputs["AnalysisStateMachineArn"], analysis_id)
        execution_history = _execution_evidence(stepfunctions, execution["executionArn"])
        checks["stepFunctions"] = {
            "executionStatus": execution["status"],
            "retryPolicies": policies,
            "allRetryPoliciesValid": all(row["valid"] for row in policies.values()),
            "history": execution_history,
            "note": "Retry policy is validated from the deployed definition; service retries are reported only if naturally observed.",
        }
        semantic_errors = [
            row for row in analysis.get("findings", [])
            if row.get("checkId") == "semantic.comparison" and row.get("status") == "ERROR"
        ]
        checks["bedrockResponseValidation"] = {
            "analysisStatus": analysis.get("status"),
            "strictResponseAccepted": not semantic_errors,
            "semanticErrorFindings": len(semantic_errors),
        }
        report_payload, _ = api_a.request("GET", f"/analyses/{analysis_id}/report")
        checks["report"] = {
            "generated": bool(report_payload.get("generatedAt")),
            "humanReviewDisclaimer": "Human review required" in report_payload.get("disclaimer", ""),
        }

        if not args.skip_failure_case:
            invalid_path = Path(f"/tmp/claimlens-invalid-{uuid.uuid4().hex}.pdf")
            invalid_path.write_bytes(b"%PDF-1.4\nSynthetic malformed acceptance file\n%%EOF\n")
            try:
                bad_claim, bad_document = _upload_document(api_a, requests, invalid_path)
                bad_analysis = _wait_analysis(api_a, _start_analysis(api_a, bad_claim, bad_document), args.timeout)
                checks["textractFailureHandling"] = {
                    "terminalStatus": bad_analysis.get("status"),
                    "neverReportedClean": bad_analysis.get("status") != "COMPLETED",
                    "warningsOrFailure": bad_analysis.get("status") in {"COMPLETED_WITH_WARNINGS", "FAILED"},
                }
            finally:
                invalid_path.unlink(missing_ok=True)
        else:
            checks["textractFailureHandling"] = {"skipped": True}

        checks["cognito"]["logout"] = _logout_verified(cognito, refreshed["accessToken"])
        critical = [
            checks["cognito"]["login"], checks["cognito"]["refresh"], checks["cognito"]["logout"],
            checks["tenantIsolation"]["blocked"], checks["signedSource"]["isPdf"],
            checks["signedSource"]["exactSourceMatch"], checks["sourceHighlighting"]["allCitationGeometryValid"],
            checks["textract"]["status"] in {"SUCCEEDED", "PARTIAL_SUCCESS"},
            checks["stepFunctions"]["executionStatus"] == "SUCCEEDED",
            checks["stepFunctions"]["allRetryPoliciesValid"],
            checks["bedrockResponseValidation"]["strictResponseAccepted"],
            checks["report"]["generated"], checks["report"]["humanReviewDisclaimer"],
        ]
        if not args.skip_failure_case:
            critical.append(checks["textractFailureHandling"]["warningsOrFailure"])
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "scope": "Live AWS acceptance using synthetic documents and temporary reviewers only.",
            "stack": args.stack,
            "region": args.region,
            "elapsedSeconds": round(time.monotonic() - started_at, 3),
            "checks": checks,
            "ready": all(critical),
            "limitations": [
                "A configured retry policy is proven; a real transient AWS service fault may not occur during this run.",
                "This synthetic acceptance is not authorization to process protected health information.",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"output": str(args.output), "checks": checks, "ready": report["ready"]}, indent=2))
        return 0 if report["ready"] else 1
    finally:
        if not args.keep_users:
            for user in users:
                try:
                    cognito.admin_delete_user(UserPoolId=outputs["UserPoolId"], Username=user["username"])
                except Exception as exc:
                    print(f"Warning: could not remove a temporary synthetic user ({type(exc).__name__})", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
