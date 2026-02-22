#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
"""Open Brave, log in to Nextcloud, and land on a selected app page."""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_URL = "http://192.168.178.75:8080"
DASHBOARD_URL = f"{BASE_URL}/apps/dashboard/"
CALENDAR_URL = f"{BASE_URL}/apps/calendar/timeGridWeek/now"
PHOTOS_URL = f"{BASE_URL}/apps/photos/"
USERNAME = "christian"
PASSWORD_FILE = Path("/home/christian/Opt/PasswordQuickAccess.enc")
DEBUG_PORT = 9223

# Typical selectors across Nextcloud/ownCloud-style login pages.
USERNAME_SELECTORS = ["#user", "input[name='user']", "input[type='text']"]
PASSWORD_SELECTORS = ["#password", "input[name='password']", "input[type='password']"]
LOGIN_BUTTON_SELECTORS = ["#submit", "button[type='submit']", "input[type='submit']"]


def wait_for_port(host: str, port: int, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def fill_first_visible(page, selectors: list[str], value: str) -> bool:
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count() > 0 and locator.is_visible():
            locator.fill(value)
            return True
    return False


def click_first_visible(page, selectors: list[str]) -> bool:
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count() > 0 and locator.is_visible():
            locator.click()
            return True
    return False


def get_brave_binary() -> str:
    return "/usr/bin/brave-browser"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open Nextcloud in Brave and log in.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
            "--calendar",
            action="store_true",
            help="Open Nextcloud Calendar after login.",
            )
    group.add_argument(
            "--photos",
            action="store_true",
            help="Open Nextcloud Photos after login.",
            )
    return parser.parse_args()


def get_target_url(args: argparse.Namespace) -> str:
    if args.calendar:
        return CALENDAR_URL
    if args.photos:
        return PHOTOS_URL
    return DASHBOARD_URL


def main() -> None:
    args = parse_args()
    target_url = get_target_url(args)

    password = PASSWORD_FILE.read_text(encoding="utf-8").strip()
    if not password:
        raise RuntimeError(f"Password file is empty: {PASSWORD_FILE}")

    brave_bin = get_brave_binary()

    # Keep a dedicated profile dir for this launched instance. We intentionally
    # do not auto-delete it because Brave should stay open after this script exits.
    profile_dir = tempfile.mkdtemp(prefix="brave-nextcloud-login-")
    brave_process = subprocess.Popen(
            [
                brave_bin,
                f"--remote-debugging-port={DEBUG_PORT}",
                #f"--user-data-dir={profile_dir}",
                "--new-window",
                f"--app={target_url}",
                ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            )

    if not wait_for_port("127.0.0.1", DEBUG_PORT, timeout_seconds=10):
        raise RuntimeError("Brave remote debugging port did not become available.")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto(target_url, wait_until="domcontentloaded")
            page.wait_for_selector(", ".join(USERNAME_SELECTORS), timeout=15_000)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Login form did not appear in time.") from exc

        if not fill_first_visible(page, USERNAME_SELECTORS, USERNAME):
            raise RuntimeError("Could not find a visible username field.")

        if not fill_first_visible(page, PASSWORD_SELECTORS, password):
            raise RuntimeError("Could not find a visible password field.")

        if not click_first_visible(page, LOGIN_BUTTON_SELECTORS):
            raise RuntimeError("Could not find a visible login button.")

        page.wait_for_timeout(1_500)
        browser.close()

    # Keep Brave running after automation is complete.
    if brave_process.poll() is not None:
        raise RuntimeError("Brave exited unexpectedly during login automation.")


if __name__ == "__main__":
    main()
