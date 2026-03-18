from pathlib import Path
import os
import shlex
import subprocess


WORKING_DIRECTORY = Path({{SUB_PATH}})


def parse_command(command: str) -> list[str]:
    return shlex.split(command, posix=os.name != "nt")


def run_command(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(parse_command(command), cwd=WORKING_DIRECTORY, check=False)
