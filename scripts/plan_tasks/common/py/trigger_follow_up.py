from __future__ import annotations

{{EXECUTION_SUPPORT}}

import subprocess


def main() -> int:
    command = ["trigger-plan", {{TARGET_PLAN_KEY}}]
    result = subprocess.run(command, check=False)
    finish_execution_if_configured(
        success=result.returncode == 0,
        result_status="successful" if result.returncode == 0 else "failed",
        summary_message="Build pipeline completed successfully." if result.returncode == 0 else "Follow-up trigger failed.",
        stage_name="Trigger Follow-up",
        job_name="Follow-up Trigger",
        task_name="trigger_follow_up.py",
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
