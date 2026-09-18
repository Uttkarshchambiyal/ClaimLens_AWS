"""Repeatable local acceptance checks. Never deploys or invokes AWS services."""
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ('dependency_check', [sys.executable, '-m', 'pip', 'check'], ROOT),
    ('backend_compile', [sys.executable, '-m', 'compileall', '-q', 'backend', 'scripts'], ROOT),
    ('backend_tests', [sys.executable, '-m', 'pytest', 'backend/tests', '-o', 'addopts=', '-q'], ROOT),
    ('sam_lint', [str(Path(sys.executable).parent / 'cfn-lint'), 'template.yaml'], ROOT),
    ('verifier_syntax', ['bash', '-n', 'scripts/verify_aws.sh'], ROOT),
    ('frontend_tests', ['npm', 'test'], ROOT / 'frontend'),
    ('production_build', ['npm', 'run', 'build'], ROOT / 'frontend'),
    ('formatting', ['npm', 'run', 'format:check'], ROOT / 'frontend'),
    ('browser_smoke', [sys.executable, 'scripts/browser_smoke.py'], ROOT),
]


def main():
    results = []
    for name, command, cwd in CHECKS:
        try:
            result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)
            status = 'PASS' if result.returncode == 0 else 'FAIL'
            output = (result.stdout + result.stderr)[-14000:]
        except (OSError, subprocess.TimeoutExpired) as error:
            status, output = 'ERROR', type(error).__name__
        results.append({'check': name, 'status': status, 'output': output})
        print(f'{name}: {status}', flush=True)
    report = {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'scope': 'Local tests, static validation, and mock browser acceptance only; no deployment or live cloud verification.',
        'checks': results,
        'awsCliAvailable': bool(shutil.which('aws')),
        'samCliAvailable': bool(shutil.which('sam')),
        'liveAwsVerified': False,
        'browserSmokeVerified': next((r['status'] == 'PASS' for r in results if r['check'] == 'browser_smoke'), False),
        'browserVisualVerified': os.getenv('CLAIMLENS_BROWSER_VISUAL_VERIFIED') == '1',
        'readiness': 'LOCAL_CHECKS_PASS_CLOUD_GATE_PENDING' if all(r['status'] == 'PASS' for r in results) else 'LOCAL_CHECKS_FAILED',
    }
    path = ROOT / 'docs' / 'verification-results.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Report: {path}')
    return 0 if all(r['status'] == 'PASS' for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
