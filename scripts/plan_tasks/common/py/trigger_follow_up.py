from __future__ import annotations

import subprocess


def main() -> int:
    command = ["trigger-plan", {{TARGET_PLAN_KEY}}]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
