from __future__ import annotations

{{COMMAND_SUPPORT}}


COMMANDS = [
{{CUSTOM_TOOL_COMMANDS}}
]


def main() -> int:
{{PRE_RUN}}
    for command in COMMANDS:
        result = run_command(command)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
