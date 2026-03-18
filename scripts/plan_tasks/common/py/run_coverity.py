from __future__ import annotations

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
        return subprocess.run(command, cwd=WORKING_DIRECTORY, check=False).returncode
    finally:
        if config_path.exists():
            config_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
