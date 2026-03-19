from __future__ import annotations

{{EXECUTION_SUPPORT}}

from pathlib import Path
import subprocess
import tempfile


WORKING_DIRECTORY = Path({{SUB_PATH}})
CONFIG_CONTENT = {{COVERITY_CONFIG}}


def main() -> int:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yaml", delete=False) as config_file:
        config_file.write(CONFIG_CONTENT)
        config_path = Path(config_file.name)

    try:
        command = ["coverity", "scan", "--config", str(config_path)]
        result = subprocess.run(command, cwd=WORKING_DIRECTORY, check=False)
        record_static_analysis_result(
            "coverity",
            "passed" if result.returncode == 0 else "failed",
            "Coverity scan completed successfully." if result.returncode == 0 else "Coverity scan failed.",
        )
        if result.returncode != 0:
            finish_execution_if_configured(
                success=False,
                result_status="failed",
                summary_message="Coverity scan failed.",
                stage_name="Static Analysis",
                job_name="Coverity Scan",
                task_name="run_coverity.py",
            )
        return result.returncode
    finally:
        if config_path.exists():
            config_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
