#!/usr/bin/env python3
from __future__ import annotations

import subprocess


def main() -> int:
    command = ["trigger-plan", "POSTBUILD"]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
