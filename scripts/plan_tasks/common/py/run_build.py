#!/usr/bin/env python3
from __future__ import annotations

{{COMMAND_SUPPORT}}


def main() -> int:
    command = {{BUILD_COMMAND}}
{{PRE_RUN}}
    return run_command(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
