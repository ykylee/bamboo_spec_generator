#!/usr/bin/env python3
from __future__ import annotations

import subprocess


def main() -> int:
    command = ["coverity", "scan", "--config", "coverity/sample-app-web/coverity.yaml"]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
