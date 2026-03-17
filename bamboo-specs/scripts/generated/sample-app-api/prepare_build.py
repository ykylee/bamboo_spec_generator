#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import subprocess


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def main() -> int:
    command = 'python scripts/prepare_build.py --tool maven'
    return subprocess.run(parse_command(command), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
