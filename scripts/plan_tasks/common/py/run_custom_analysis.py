from __future__ import annotations

{{COMMAND_SUPPORT}}
{{EXECUTION_SUPPORT}}


COMMANDS = [
{{CUSTOM_TOOL_COMMANDS}}
]


def main() -> int:
    start_execution_if_configured()
{{PRE_RUN}}
    for command in COMMANDS:
        result = run_command(command)
        if result.returncode != 0:
            record_static_analysis_result(
                "custom-tool",
                "failed",
                "Custom analysis failed.",
            )
            finish_execution_if_configured(
                success=False,
                result_status="failed",
                summary_message="Custom analysis failed.",
                stage_name="Static Analysis",
                job_name="Custom Analysis",
                task_name="run_custom_analysis.py",
            )
            return result.returncode
    record_static_analysis_result(
        "custom-tool",
        "passed",
        "Custom analysis completed successfully.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
