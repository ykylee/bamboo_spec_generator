from __future__ import annotations

{{COMMAND_SUPPORT}}


def main() -> int:
    command = {{PREPARE_COMMAND}}
{{PRE_RUN}}
    return run_command(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
