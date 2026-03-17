#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import subprocess


COMMANDS = [
        'python scripts/custom_tool.py init',
        'custom-tool analyze python scripts/run_build.py --tool maven --goal package',
        'python scripts/custom_tool.py publish'
]


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def main() -> int:
    for command in COMMANDS:
        result = subprocess.run(parse_command(command), check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
