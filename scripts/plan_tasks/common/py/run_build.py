from __future__ import annotations

{{COMMAND_SUPPORT}}
{{EXECUTION_SUPPORT}}


def main() -> int:
    start_execution_if_configured()
    command = {{BUILD_COMMAND}}
{{PRE_RUN}}
    result = run_command(command)
    if result.returncode != 0:
        finish_execution_if_configured(
            success=False,
            result_status="failed",
            summary_message="Build stage failed.",
            stage_name="Build",
            job_name="Build",
            task_name="run_build.py",
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
