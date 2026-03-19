from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAYWRIGHT_ARTIFACT_DIR = REPO_ROOT / ".playwright-cli"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture a UI screenshot using Playwright CLI with a repo-safe Firefox configuration.",
    )
    parser.add_argument("url", help="Target URL to open before capturing the screenshot.")
    parser.add_argument(
        "--output",
        default="output/playwright/ui-screenshot.png",
        help="Output PNG path relative to the repository root.",
    )
    parser.add_argument(
        "--session",
        default="bamboo-ui-capture",
        help="Playwright CLI session name.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=2560,
        help="Viewport width in pixels. Defaults to QHD width.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1440,
        help="Viewport height in pixels. Defaults to QHD height.",
    )
    args = parser.parse_args()

    if shutil.which("npx") is None:
        print("npx is required but was not found on PATH.", file=sys.stderr)
        return 1

    output_path = (REPO_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    PLAYWRIGHT_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    install_cmd = ["npx", "--yes", "--package", "playwright", "playwright", "install", "firefox"]
    _run(install_cmd, cwd=REPO_ROOT)

    env = {
        **os.environ,
        "PLAYWRIGHT_CLI_SESSION": args.session,
    }
    open_cmd = [
        "npx",
        "--yes",
        "--package",
        "@playwright/cli",
        "playwright-cli",
        "open",
        args.url,
        "--browser",
        "firefox",
    ]
    _run(open_cmd, cwd=REPO_ROOT, env=env)

    try:
        resize_cmd = [
            "npx",
            "--yes",
            "--package",
            "@playwright/cli",
            "playwright-cli",
            "resize",
            str(args.width),
            str(args.height),
        ]
        _run(resize_cmd, cwd=REPO_ROOT, env=env)

        before = _latest_screenshot_timestamp()
        screenshot_cmd = [
            "npx",
            "--yes",
            "--package",
            "@playwright/cli",
            "playwright-cli",
            "screenshot",
        ]
        _run(screenshot_cmd, cwd=REPO_ROOT, env=env)

        screenshot_path = _wait_for_new_screenshot(before)
        shutil.copy2(screenshot_path, output_path)
        print(f"Saved screenshot to: {output_path}")
    finally:
        close_cmd = [
            "npx",
            "--yes",
            "--package",
            "@playwright/cli",
            "playwright-cli",
            "close",
        ]
        subprocess.run(close_cmd, cwd=REPO_ROOT, env=env, check=False, text=True)
    return 0


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(cmd, cwd=cwd, env=env, check=False, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _latest_screenshot_timestamp() -> float:
    screenshots = list(PLAYWRIGHT_ARTIFACT_DIR.glob("*.png"))
    if not screenshots:
        return 0.0
    return max(path.stat().st_mtime for path in screenshots)


def _wait_for_new_screenshot(previous_timestamp: float) -> Path:
    deadline = time.time() + 10
    while time.time() < deadline:
        screenshots = sorted(PLAYWRIGHT_ARTIFACT_DIR.glob("*.png"), key=lambda path: path.stat().st_mtime, reverse=True)
        if screenshots and screenshots[0].stat().st_mtime > previous_timestamp:
            return screenshots[0]
        time.sleep(0.2)
    raise SystemExit("Playwright screenshot was not generated within the expected time.")


if __name__ == "__main__":
    raise SystemExit(main())
