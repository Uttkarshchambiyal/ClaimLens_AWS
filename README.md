# ClaimLens

A human-in-the-loop medical claim integrity review prototype. ClaimLens compares an itemized bill, discharge summary, and supporting reports, and presents traceable evidence for a reviewer. It never produces fraud probabilities or approves, rejects, or pays claims.

## Run locally

Use Node.js 22+ and Python 3.11+. All demo patients and providers are fictional.

```bash
cd frontend
npm ci
npm run dev
```

- `/`: clean split-image Aero landing page, sample preview, and working workspace links.
- `/review`: reviewer workspace, labeled **MOCK MODE** during local development.
- `/auth/login`: first-party login form backed directly by Cognito.
- `/auth/signup`: first-party account creation and email-code verification.
- `/auth/callback`: legacy managed-login callback retained for deployment compatibility.

The reviewer workspace includes inconsistent, consistent, ambiguous, and legitimate edge-case scenarios; the rule benchmark also includes an explicit-adjustments packet. Demo reviewer actions and correction annotations persist in this browser's session storage. Demo uploads do **not** perform OCR or fabricate findings; they record an explicit extraction-unavailable result. Use synthetic files only.

## Frontend structure and hero integration

React, TypeScript, Tailwind CSS v4, Lucide icons, and a shadcn-compatible layout are configured:

```text
frontend/
  components.json
  src/
    components/ui/aero-hero-1.tsx
    components/ui/glassmorphism-trust-hero.tsx (compatibility export)
    components/demo.tsx
    lib/utils.ts
    theme.css
    hero.css
    styles.css
```

`@/` resolves to `frontend/src/`. Therefore the component path `@/components/ui` means `frontend/src/components/ui`, not a second folder at the repository root. This directory keeps reusable UI separate from application screens and matches the aliases used by shadcn-generated components. No context provider is needed for the hero.

`HeroSection` accepts optional `reviewHref` and `className` props. Its sample dialog and animation pause control use local React state. The layout stacks below the large-screen breakpoint, respects reduced-motion preferences, and includes keyboard focus states. Sample metrics are explicitly synthetic; the AWS strip describes the intended architecture, not customers or verified service access.

Tailwind's Vite plugin is registered in `vite.config.ts`. `theme.css` owns the shared paper, charcoal, and lime palette, typography, focus states, and surface tokens; `hero.css` imports Tailwind and defines the split-image landing layout. `styles.css` applies the same clear cards, pill controls, selected states, and palette to the queue, review, activity, documents, source viewer, dialogs, and notifications. Mobile queues reduce the desktop table to the three decision-relevant columns. Original PDF/image pages retain their own colors so their contents are not altered. Reviewer CSS is lazy-loaded with the workspace. The Unsplash healthcare image is bundled locally; attribution is in `public/images/ATTRIBUTION.md`, so visitors do not need an external image request.

Workspace navigation stores the selected analysis and view in the URL, supports Back/Forward, and clears screen-specific search text. The ClaimLens logo returns home. Review tabs support arrow keys, Home, and End. Small screens use labeled horizontal navigation and a dismissible source drawer. A failed correction stays in the form for retry without replacing the visible source.

Setup has already been applied; do not run a new project initializer over this app. To add shadcn components later, run from `frontend/`:

```bash
npx shadcn@latest add button
```

For a new checkout, `npm ci` installs TypeScript, Tailwind, Lucide, and the configured dependencies. Reference setup: [Tailwind with Vite](https://tailwindcss.com/docs/installation/using-vite), [shadcn with Vite](https://ui.shadcn.com/docs/installation/vite).

## Local verification

```bash
# Repository root
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest backend/tests
.venv/bin/python scripts/evaluate_quality.py
.venv/bin/python scripts/benchmark_large_packet.py
.venv/bin/cfn-lint template.yaml
.venv/bin/python -m pip_audit -r backend/requirements.txt
.venv/bin/python -m pip_audit -r requirements-dev.txt
bash -n scripts/verify_aws.sh

# Frontend directory
npm test
npm run format:check
npm run build
npm audit --audit-level=high
```

The full verifier also launches Chromium and exercises the explicit mock journey at desktop and mobile widths:

```bash
.venv/bin/python scripts/verify_project.py
```

Backend tests include real SDK serialization against **Moto-emulated** DynamoDB/S3, conditional idempotency leases, tenant boundaries, pinned S3 versions, and API upload-to-report orchestration with injected synthetic extraction. Moto is not evidence of AWS permissions, live Textract, or live Bedrock behavior. Frontend tests cover filters, queue switching, URL restoration, keyboard tabs, document-to-evidence navigation, reviewer actions, correction failures/retry, the upload dialog, duplicate demo requests, report-download initiation, hero links, sample dialog, and animation controls.

## AWS configuration and deployment

`template.yaml` defines Python Lambda/API Gateway, private versioned S3, DynamoDB, Cognito, Step Functions Standard, Textract permissions, bounded Bedrock comparison, and optional S3/CloudFront hosting. The hackathon stack is deployed in `ap-south-1` with CloudFront disabled because the new account is still awaiting CloudFront verification; Amplify Hosting serves the production frontend instead.

```bash
sam build
sam validate --lint
sam deploy --guided --region <your-region>
```

Set `BedrockModelId`, `RetentionDays`, `LogRetentionDays`, and `MinFieldConfidence` for the chosen environment. `AllowedOrigin`, `CognitoCallbackUrl`, and `CognitoLogoutUrl` automatically use the generated CloudFront URL when left blank. To use Amplify or another HTTPS host, deploy with `EnableCloudFront=false` and provide all three URL parameters. Verify the selected model's regional availability. Cognito stores credentials, verifies self-registered email addresses, and supports administrator-provisioned reviewers. A pre-token hook preserves an assigned `custom:tenant_id` or derives a private tenant from the immutable Cognito subject for a new self-service user. The browser cannot choose its tenant. The API requires an API-Gateway-validated ID token containing that tenant claim.

Frontend variables are in `frontend/.env.example`. Set `VITE_APP_MODE=production` and the deployed API/Cognito values for AWS use. Builds default to production unless mock mode is explicitly selected. Production never silently falls back to fabricated findings. For a deliberately labeled static demo, use `npm run build:demo`.

Configure the frontend host to serve `index.html` for `/review`, `/auth/login`, `/auth/signup`, and `/auth/callback`. Keep the configured callback host, scheme, and port consistent with Cognito.

## AWS verification status

**Partially verified against AWS.** The stack is `UPDATE_COMPLETE` in `ap-south-1`, and the production frontend is live at [main.d32my0bksmpqr2.amplifyapp.com](https://main.d32my0bksmpqr2.amplifyapp.com). A tenant-scoped Cognito reviewer successfully completed hosted login, authorization-code callback, and a protected empty-queue API request with no browser errors. Lambda, API Gateway, Step Functions, S3, DynamoDB, Cognito, CloudWatch, and Amplify resources are deployed. Textract still returns `SubscriptionRequiredException`, and Bedrock invocation returns `Operation not allowed`; AWS account/model activation must complete before document analysis can pass.

Once CLI credentials and your selected region/model are available:

```bash
AWS_REGION=<region> BEDROCK_MODEL_ID=<model-id> ./scripts/verify_aws.sh
```

The script checks STS identity, probes Textract GetDocumentAnalysis, and sends a minimal synthetic Bedrock Converse request (which may incur usage charges). It reports subscription/account activation errors separately from IAM denial. An invalid-job response proves API reachability only, not StartDocumentAnalysis permission. Full S3 upload, Step Functions execution, Textract extraction, Bedrock comparison, source rendering, and cross-tenant denial still need deployed integration tests.

## Implemented safeguards and known limits

- Integer-paise reconciliation separates invoice total, payment, balance, and claimed amount. Conflicting totals and ambiguous normalization cannot become clean results.
- Explicit GST/tax, discount and signed round-off rows are normalized as invoice adjustments. Repeated table headers and subtotal/total rows are excluded from line-item sums.
- Extracted fields below the configurable confidence threshold defaulting to 80 are marked `LOW_CONFIDENCE`; they cannot produce a clean deterministic result.
- Source references retain document/version, page, block IDs, geometry, and extraction confidence. Invalid model citations are rejected; unavailable AI produces an error check alongside deterministic results.
- S3 is private, encrypted, and versioned. Analysis pins the uploaded S3 version. DynamoDB records and all API lookups are tenant-scoped.
- Browser uploads use presigned POST policies that enforce the declared content type, AES256 encryption, and a 1-byte-to-15-MB size range before S3 accepts the object.
- Current and noncurrent S3 objects, DynamoDB records, idempotency records, and Lambda logs have explicit deployment-configurable retention. DynamoDB TTL deletion is asynchronous.
- Model inputs are bounded and treated as untrusted data. The model has no tools, external browsing, or write access. Routine logs contain error categories, not medical content.
- Original extraction and analysis snapshots are preserved. Corrections are **annotations only**: they appear in reports but do not yet rerun normalization or checks.
- Reviewer dispositions persist separately from automated findings. Every disposition change is also appended to an immutable `REVIEW_EVENT` record with the authenticated Cognito subject; correction annotations carry the same actor ID. JSON reports contain the current state and audit activity. There is no cryptographically signed report yet.
- Production source viewing renders PDF/image bytes with evidence overlays; this is implemented but unverified against a live signed S3 URL. Mock mode shows a labeled synthetic evidence sheet, not an original document.
- Textract normalization supports expanded English/Hindi labels, repeated table headers, explicit adjustments and common procedure abbreviations, but not arbitrary hospital layouts. Ambiguous values still require review. Live OCR accuracy and end-to-end cloud failure recovery remain deployment gates.
- Historical matching finds deterministic invoice candidates, not proof of duplicate payment or fraud.

See [architecture](docs/architecture.md) and [acceptance checks](docs/acceptance.md).

The [evaluation protocol](docs/evaluation.md) adds measurable rule precision/recall, a maximum-shape local packet benchmark, an eight-page visually verified OCR corpus, and a live Textract/Bedrock evaluator. Local reports are `docs/quality-benchmark-results.json` and `docs/large-packet-benchmark.json`; live accuracy remains unverified until `scripts/evaluate_live_aws.py` is run with AWS access.

## Hackathon guide and repeatable readiness checks

The [14-page project guide](output/pdf/claimlens-architecture-and-readiness.pdf) explains the website, AWS architecture, component responsibilities, evidence/record model, rules, model boundary, security, reliability, demo script, and live acceptance gate. Its editable source is [docs/claimlens-guide.md](docs/claimlens-guide.md).

Current local results: **68 backend tests and 16 frontend tests pass**, along with the labeled quality benchmark, maximum-shape packet benchmark, eight-page evaluation-artifact validation, dependency consistency, Python compilation, production build, formatting, SAM lint, verifier syntax, and desktop/mobile Chromium acceptance. The eight evaluation pages and nine application screenshots were visually inspected. Current npm and all three Python requirement audits report no known vulnerabilities. AWS hosting, Cognito login, and a protected API read are verified; live self-registration acceptance, Textract/Bedrock processing, and production signed-source verification remain outstanding. This is a synthetic hackathon prototype, not a certified production-ready medical system. Event-specific eligibility cannot be confirmed without the hackathon rules.

```bash
.venv/bin/python scripts/verify_project.py
# Rebuild the guide after refreshing verification results:
.venv/bin/python -m pip install -r requirements-docs.txt
.venv/bin/python scripts/build_project_guide.py
```

`docs/verification-results.json` records the check outputs and timestamp. `.github/workflows/verify.yml` defines a local-acceptance CI job but has not run remotely yet. PDF rendering uses PyMuPDF when Poppler is unavailable; inspect the generated page images before delivering an updated guide.
