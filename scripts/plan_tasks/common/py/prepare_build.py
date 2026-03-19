from __future__ import annotations

{{COMMAND_SUPPORT}}
{{EXECUTION_SUPPORT}}


def main() -> int:
{{PREPARE_CONTEXT_EXPORTS}}
    start_execution_if_configured()
    command = {{PREPARE_COMMAND}}
{{PRE_RUN}}
    result = run_command(command)
    if result.returncode != 0:
        finish_execution_if_configured(
            success=False,
            result_status="failed",
            summary_message="Prepare stage failed.",
            stage_name="Prepare",
            job_name="Prepare",
            task_name="prepare_build.py",
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
