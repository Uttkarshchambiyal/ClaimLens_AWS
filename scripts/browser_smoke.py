"""Headless browser acceptance for the explicit local mock experience."""

from __future__ import annotations

import argparse
from contextlib import closing
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _port() -> int:
    with closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, process: subprocess.Popen, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Vite stopped before the browser check could start")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.15)
    raise RuntimeError("Timed out waiting for the local Vite server")


def _assert_page_basics(page: Page) -> None:
    problems = page.evaluate(
        """() => {
          const ids = [...document.querySelectorAll('[id]')].map((node) => node.id)
          const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index)
          const unlabeledImages = [...document.images].filter((img) => !img.hasAttribute('alt'))
          return {
            duplicateIds: [...new Set(duplicates)],
            unlabeledImages: unlabeledImages.length,
            horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
          }
        }"""
    )
    if problems["duplicateIds"]:
        raise AssertionError(f"Duplicate DOM ids: {problems['duplicateIds']}")
    if problems["unlabeledImages"]:
        raise AssertionError("One or more images are missing alt text")
    if problems["horizontalOverflow"]:
        raise AssertionError("The page has viewport-level horizontal overflow")


def _screenshot(page: Page, directory: Path | None, name: str) -> None:
    if directory:
        page.screenshot(path=directory / name, full_page=True)


def _desktop_flow(page: Page, base_url: str, artifacts: Path | None) -> None:
    page.goto(base_url, wait_until="networkidle")
    page.get_by_role("heading", name=re.compile(r"Every claim.*Clear evidence.*Confident review")).wait_for()
    _assert_page_basics(page)
    _screenshot(page, artifacts, "desktop-landing.png")

    page.goto(base_url + "/auth/login", wait_until="networkidle")
    page.get_by_role("heading", name="Log in").wait_for()
    page.get_by_role("link", name="Create account").wait_for()
    _assert_page_basics(page)
    _screenshot(page, artifacts, "desktop-login.png")

    page.goto(base_url + "/auth/signup", wait_until="networkidle")
    page.get_by_role("heading", name="Create your account").wait_for()
    page.get_by_role("link", name="Log in").wait_for()
    _assert_page_basics(page)
    _screenshot(page, artifacts, "desktop-signup.png")

    page.goto(base_url, wait_until="networkidle")
    page.get_by_role("link", name="Open sample workspace").click()
    page.wait_for_url("**/review")
    page.get_by_role("heading", name="Invoice total does not reconcile").wait_for()
    page.get_by_role("button", name="Review queue").click()
    page.get_by_role("heading", name="Review queue").first.wait_for()
    page.get_by_role("button", name=re.compile(r"^CLM-20481")).click()
    page.get_by_role("heading", name="Invoice total does not reconcile").wait_for()
    page.get_by_role("button", name="Acknowledged").click()
    page.get_by_text("Review disposition saved.").wait_for()
    page.get_by_role("button", name="View source A, CityCare_itemized_bill.pdf, page 3").click()
    page.get_by_label("Document source viewer").wait_for()
    _assert_page_basics(page)
    _screenshot(page, artifacts, "desktop-review.png")

    page.get_by_role("button", name="Close source viewer").click()
    page.get_by_role("button", name="Review activity").click()
    page.get_by_text("Reviewer demo-reviewer").wait_for()
    page.get_by_role("button", name="New packet").click()
    page.get_by_role("heading", name="Start a new review").wait_for()
    _assert_page_basics(page)
    _screenshot(page, artifacts, "desktop-upload.png")
    page.get_by_role("button", name="Close upload").click()


def _mobile_flow(page: Page, base_url: str, artifacts: Path | None) -> None:
    page.goto(base_url, wait_until="networkidle")
    page.get_by_role("heading", name=re.compile(r"Every claim.*Clear evidence.*Confident review")).wait_for()
    _assert_page_basics(page)
    _screenshot(page, artifacts, "mobile-landing.png")

    page.goto(base_url + "/auth/signup", wait_until="networkidle")
    page.get_by_role("heading", name="Create your account").wait_for()
    _assert_page_basics(page)
    _screenshot(page, artifacts, "mobile-signup.png")

    page.goto(base_url + "/review", wait_until="networkidle")
    page.get_by_role("heading", name="Invoice total does not reconcile").wait_for()
    page.get_by_role("button", name="Review queue").click()
    page.get_by_role("heading", name="Review queue").first.wait_for()
    _assert_page_basics(page)
    _screenshot(page, artifacts, "mobile-queue.png")
    page.get_by_role("button", name=re.compile(r"^CLM-20481")).click()
    page.get_by_role("heading", name="Invoice total does not reconcile").wait_for()
    page.get_by_role("button", name="View source A, CityCare_itemized_bill.pdf, page 3").click()
    page.get_by_role("dialog", name="Document source viewer").wait_for()
    _assert_page_basics(page)
    _screenshot(page, artifacts, "mobile-source.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, help="Optional directory for QA screenshots")
    args = parser.parse_args()
    if args.artifacts:
        args.artifacts.mkdir(parents=True, exist_ok=True)

    port = _port()
    base_url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(port), "--strictPort"],
        cwd=FRONTEND,
        env={**os.environ, "VITE_APP_MODE": "mock"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_server(base_url, process)
        browser_errors: list[str] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            desktop = browser.new_page(viewport={"width": 1536, "height": 960})
            desktop.on("pageerror", lambda error: browser_errors.append(str(error)))
            desktop.on(
                "console",
                lambda message: browser_errors.append(message.text) if message.type == "error" else None,
            )
            _desktop_flow(desktop, base_url, args.artifacts)
            mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
            mobile.on("pageerror", lambda error: browser_errors.append(str(error)))
            mobile.on(
                "console",
                lambda message: browser_errors.append(message.text) if message.type == "error" else None,
            )
            _mobile_flow(mobile, base_url, args.artifacts)
            browser.close()
        if browser_errors:
            raise AssertionError("Browser errors: " + " | ".join(browser_errors))
        print("browser_smoke: PASS (desktop and mobile mock workflows)")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
